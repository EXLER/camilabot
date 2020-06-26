import os

import discord
from discord.ext import commands

from utils import log, web


class Music(commands.Cog):
    """
    Play music from YouTube videos, directly with a link or by searching.
    """

    def __init__(self, bot):
        self.bot = bot

        if os.path.isdir("data/audio"):
            for file in os.listdir("data/audio"):
                os.remove(f"data/audio/{file}")
        os.makedirs("data/audio", exist_ok=True)

        self.voice_channels = {}
        self.voice_queues = {}

    @commands.command()
    async def join(self, ctx):
        """Join the room occupied by the person invoking the command.
           usage: !join"""
        if ctx.author.voice:
            if (
                not ctx.voice_client
                or ctx.author.voice.channel != ctx.voice_client.channel
            ):
                self.voice_channels[
                    ctx.message.guild.id
                ] = await ctx.author.voice.channel.connect()
                self.voice_queues[ctx.message.guild.id] = []
        else:
            await ctx.send("You are not in any voice channel!")

    @commands.command()
    async def play(self, ctx, *, video):
        """Play music from a YouTube video"""
        await self.join(ctx)
        await ctx.send("📺 Trying to get the video...")

        audio_info = web.youtube_download(video)
        self.voice_queues[ctx.message.guild.id].append(audio_info)

        if len(self.voice_queues[ctx.message.guild.id]) == 1:
            await ctx.send(f"▶️ Now playing: {audio_info['title']}")
            self.queue(ctx.message.guild.id, 0)
        elif len(self.voice_queues[ctx.message.guild.id]) > 1:
            await ctx.send(
                f"#️⃣ Added `{audio_info['title']}` to queue at position {len(self.voice_queues[ctx.message.guild.id]) - 1}"
            )

    @commands.command(aliases=["stop"])
    async def skip(self, ctx):
        """Skip the current playing video"""
        voice = self.voice_channels[ctx.message.guild.id]

        if voice and voice.is_playing():
            voice.stop()
            await ctx.send("⏭ Audio skipped.")
        else:
            await ctx.send("Nothing to skip.")

    @commands.command()
    async def pause(self, ctx):
        """Pause the current playing video"""
        voice = self.voice_channels[ctx.message.guild.id]

        if voice and voice.is_playing():
            voice.pause()
            await ctx.send("⏸ Audio paused. To unpause write `!unpause`.")
        else:
            await ctx.send("Nothing to pause.")

    @commands.command(aliases=["resume"])
    async def unpause(self, ctx):
        """Unpause the currently paused video"""
        voice = self.voice_channels[ctx.message.guild.id]

        if voice and voice.is_paused():
            voice.resume()
            await ctx.send("▶️ Audio unpaused.")
        else:
            await ctx.send("Nothing to unpause.")

    @commands.command()
    async def leave(self, ctx):
        """Leave the current voice channel"""
        if self.voice_channels[ctx.message.guild.id]:
            await self.voice_channels[ctx.message.guild.id].disconnect()

        if os.path.isdir("data/audio"):
            for file in os.listdir("data/audio"):
                os.remove(f"data/audio/{file}")

    def queue(self, guild_id, queue_place):
        """Plays the next audio track on the queue"""
        if queue_place < len(self.voice_queues[guild_id]):
            self.voice_channels[guild_id].play(
                discord.FFmpegPCMAudio(
                    f"data/audio/{self.voice_queues[guild_id][queue_place]['title']}.mp3"
                ),
                after=lambda e: self.queue(guild_id, queue_place + 1),
            )
        else:
            self.voice_queues[guild_id] = []


def setup(bot):
    bot.add_cog(Music(bot))
