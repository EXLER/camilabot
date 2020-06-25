import os
import random

import discord
from discord.ext import commands

from utils import log


class Randoms(commands.Cog):
    """
    Randomize between people, numbers or more!
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def randomrange(self, ctx, lower: int, upper: int):
        number = random.randint(lower, upper)
        await ctx.send(f"🎲 Your random number between {lower} and {upper} is: {number}")

    @commands.command()
    async def randommember(self, ctx, role: discord.Role):
        member = random.choice(role.members)
        await ctx.send(f"🎲 The person chosen for this is: {member}")


def setup(bot):
    bot.add_cog(Randoms(bot))
