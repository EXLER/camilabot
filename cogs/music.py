import math
import asyncio
import itertools
import functools

import youtube_dlc
import discord
from discord.ext import commands
from async_timeout import timeout

from camila.exceptions import VoiceError, YTDLError

youtube_dlc.utils.bug_reports_message = lambda: ""


class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        "format": "bestaudio/best",
        "extractaudio": True,
        "audioformat": "mp3",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

    ytdl = youtube_dlc.YoutubeDL(YTDL_OPTIONS)

    def __init__(
        self,
        ctx: commands.Context,
        source: discord.FFmpegPCMAudio,
        *,
        data: dict,
        volume: float = 0.5,
    ):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get("uploader")
        self.uploader_url = data.get("uploader_url")
        date = data.get("upload_date")
        self.upload_date = date[6:8] + "." + date[4:6] + "." + date[0:4]
        self.title = data.get("title")
        self.thumbnail = data.get("thumbnail")
        self.description = data.get("description")
        self.duration = self.parse_duration(int(data.get("duration")))
        self.tags = data.get("tags")
        self.url = data.get("webpage_url")
        self.views = data.get("view_count")
        self.likes = data.get("like_count")
        self.dislikes = data.get("dislike_count")
        self.stream_url = data.get("url")

    def __str__(self):
        return f"**{self.title}** by **{self.uploader}**"

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError(f"Nie znaleziono utworu: `{search}`")

        if "entries" not in data:
            process_info = data
        else:
            process_info = None
            for entry in data["entries"]:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError(f"Nie znaleziono utworu: `{search}`")

        webpage_url = process_info["webpage_url"]
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError(f"Nie udało się pobrać: `{webpage_url}`")

        if "entries" not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info["entries"].pop(0)
                except IndexError:
                    raise YTDLError(f"Nie udało się pobrać żadnych plików dla `{webpage_url}`")

        return cls(ctx, discord.FFmpegPCMAudio(info["url"], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append(f"{days}d")
        if hours > 0:
            duration.append(f"{hours}h")
        if minutes > 0:
            duration.append(f"{minutes}m")
        if seconds > 0:
            duration.append(f"{seconds}s")

        return ", ".join(duration)


class Song:
    __slots__ = ("source", "requester")

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = (
            discord.Embed(
                title="Aktualny utwór",
                description=f"```css\n{self.source.title}\n```",
                color=discord.Color.gold(),
            )
            .add_field(name="Długość", value=self.source.duration)
            .add_field(name="Dodane przez", value=self.requester.mention)
            .add_field(
                name="Uploader",
                value=f"[{self.source.uploader}]({self.source.uploader_url})",
            )
            .add_field(name="URL", value=f"[{self.source.url}]({self.source.url})")
            .set_thumbnail(url=self.source.thumbnail)
        )

        return embed


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._volume = 0.5

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()

            # Try to get the next song within 3 minutes
            # If no song will be added to the queue in time, the player will disconnect
            try:
                async with timeout(180):
                    self.current = await self.songs.get()
            except asyncio.TimeoutError:
                self.bot.loop.create_task(self.stop())
                return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)
            await self.current.source.channel.send(embed=self.current.create_embed())

            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(f"Error while trying to play next song: {error}")

        self.next.set()

    def skip(self):
        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None
            self.current = None


class Music(commands.Cog):
    """
    Play music from YouTube videos, directly with a link or by searching.
    """

    def __init__(self, bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)

        if not state or (state and not state.voice):
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage("This command can't be used in DM channels.")

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    @commands.command()
    async def join(self, ctx: commands.Context):
        """Make the bot join your channel"""
        destination = ctx.author.voice.channel

        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(aliases=["stop"])
    async def leave(self, ctx: commands.Context):
        """Clears the queue and makes the bot leave the voice channel"""
        if not ctx.voice_state.voice:
            return await ctx.send("Nie jestem połączona z żadnym kanałem głosowym!")

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command()
    async def volume(self, ctx: commands.Context, *, volume: int):
        """Sets the volume of the player"""
        if not ctx.voice_state.is_playing:
            return await ctx.send("Nie mogę zmienić głośności kiedy nic nie gra!")

        if 0 > volume > 100:
            return await ctx.send("Glośność musi być między 0 a 100")

        ctx.voice_state.volume = volume / 100
        await ctx.send(f"🔊 Głośność od następnego utworu będzie ustawiona na {volume}%")

    @commands.command(aliases=["current", "playing"])
    async def now(self, ctx: commands.Context):
        """Displays the currently playing song"""
        if ctx.voice_state.current:
            await ctx.send(embed=ctx.voice_state.current.create_embed())
        else:
            await ctx.send("Aktualnie nic nie gra.")

    @commands.command()
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song"""
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction("⏸️")

    @commands.command(aliases=["unpause"])
    async def resume(self, ctx: commands.Context):
        """Resumes the currently paused song"""
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction("▶️")

    @commands.command()
    async def skip(self, ctx: commands.Context):
        """Skips the currently playing song"""
        if not ctx.voice_state.is_playing:
            return await ctx.send("Nie mogę pominąć utworu kiedy nic nie gra!")

        await ctx.message.add_reaction("⏭️")
        ctx.voice_state.skip()

    @commands.command()
    async def queue(self, ctx: commands.Context, *, page: int = 1):
        """Shows the player's queue.
        You can optionally specify the page to show. Each page contains 10 elements"""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send("Kolejka jest pusta.")

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ""
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += f"`{i + 1}.` [**{song.source.title}**]({song.source.url})\n"

        embed = discord.Embed(description=f"**{len(ctx.voice_state.songs)} tracks:**\n\n{queue}").set_footer(
            text=f"Viewing page {page}/{pages}"
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue at a given index"""

        if len(ctx.voice_state.songs) == 0:
            return await ctx.send("Kolejka jest pusta.")

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction("✅")

    @commands.command()
    async def play(self, ctx: commands.Context, *, search: str):
        """Plays a song.
        If there are songs in the queue, this will be queued until the
        other songs finished playing.
        This command automatically searches from various sites if no URL is provided.
        A list of these sites can be found here: https://rg3.github.io/youtube-dl/supportedsites.html
        """
        if not ctx.voice_state.voice:
            await ctx.invoke(self.join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send("An error occurred while processing this request: {}".format(str(e)))
            else:
                song = Song(source)

                await ctx.voice_state.songs.put(song)
                await ctx.send(f"Dodano do kolejki {source}")

    @join.before_invoke
    @play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("Nie jesteś połączony z żadnym kanałem głosowym!")

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                return await ctx.send("Jestem już w innym kanale głosowym.")


def setup(bot):
    bot.add_cog(Music(bot))
