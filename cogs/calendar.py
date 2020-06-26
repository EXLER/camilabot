import discord
from discord.ext import commands
import aiosqlite3

from utils import log, validators


class Calendar(commands.Cog):
    """
    Schedule one-time or repeating events.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def schedule(self, ctx, title, group: discord.Role, *, date):
        """Schedule a new event.
        All members of given group will be mentioned in the reminder
        Date format: YYYY-MM-DD hh:mm"""
        if not validators.date_validator(date):
            await ctx.send(
                "❌ Incorrect date format or date is in the past. Please write the date in format: YYYY-MM-DD hh:mm"
            )
            return

        creator_id = ctx.author.id
        async with self.bot.db_holder.db.cursor() as cur:
            try:
                await cur.execute(
                    f'INSERT INTO events VALUES ("{creator_id}", "{title}", "{date}", "{group}")'
                )
                await self.bot.db_holder.db.commit()
                await ctx.send(
                    f"📅 Scheduled event `{title}` for group `{group}` on `{date}`"
                )
            except aiosqlite3.IntegrityError as e:
                log.error(f"Database error on `schedule` command: {e}")
                await ctx.send(
                    "Database error occured while using the `schedule` command."
                )

    @commands.command()
    async def editevent(self, title):
        """Edit an existing event.
           Can only be called by server admin or the event creator"""
        pass

    @commands.command()
    async def deleteevent(self, title):
        """Delete an existing event.
           Can only be called by server admin or the event creator"""
        pass

    @commands.command()
    async def allscheduled(self, ctx):
        pass

    @commands.command()
    async def today(self, ctx):
        pass

    @commands.command()
    async def week(self, ctx):
        pass


def setup(bot):
    bot.add_cog(Calendar(bot))
