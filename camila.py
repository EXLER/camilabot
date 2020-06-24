#!/usr/bin/env python3

import os
import configparser
from datetime import datetime
from subprocess import check_output, CalledProcessError
from traceback import format_exc

import discord
from discord.ext import commands

from utils import log, database

config = configparser.ConfigParser()
config.read("config.ini")

cogs = []
for file in os.listdir("cogs"):
    if file.endswith(".py"):
        cogs.append(f"cogs.{file[:-3]}")


class Camila(commands.Bot):
    """
    Main Bot class derived from the discord.py Bot.
    """

    def __init__(self, command_prefix, description):
        super().__init__(command_prefix=command_prefix, description=description)

        self.startup = datetime.now()

        self.failed_cogs = []
        self.exitcode = 0

        os.makedirs("data", exist_ok=True)

    def add_cog(self, cog):
        super().add_cog(cog)
        log.info(f"Cog loaded: {cog.qualified_name}")

    def load_cogs(self):
        for extension in cogs:
            try:
                self.load_extension(extension)
            except BaseException as e:
                log.warn(f"{extension} failed to load.")
                self.failed_cogs.append([extension, type(e).__name__, e])

    async def on_ready(self):
        self.db_connector = database.DatabaseConnector()
        await self.db_connector.load_db(
            config["Database"]["Path"], self.loop,
        )

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="Politechnika Śląska"
            )
        )

        startup_message = f"{self.user.name} has connected to Discord!"
        if len(self.failed_cogs) != 0:
            startup_message += "\n\nAddons failed to load:\n"
            for fail in self.failed_cogs:
                startup_message += "\n{}: `{}: {}`".format(*fail)
        log.info(startup_message)

    async def on_command_error(
        self, ctx: commands.Context, exc: commands.CommandInvokeError
    ):
        author: discord.Member = ctx.author
        command: commands.Command = ctx.command or "<unknown command>"
        exc = getattr(exc, "original", exc)

        if isinstance(exc, commands.CommandNotFound):
            await ctx.send(
                "Nie znalaziono komendy. Wpisz !help aby zobaczyć dostępne komendy."
            )
        elif isinstance(exc, commands.ArgumentParsingError):
            await ctx.send_help(ctx.command)
        elif isinstance(exc, commands.NoPrivateMessage):
            await ctx.send("Nie odpisuję na prywatne wiadomości.")
        elif isinstance(exc, commands.MissingPermissions):
            await ctx.send(f"{author.mention} Nie masz tutaj wystarczającej mocy.")
        elif isinstance(exc, commands.CheckFailure):
            await ctx.send(f"{author.mention} Nie możesz tego zrobić.")
        elif isinstance(exc, commands.BadArgument):
            await ctx.send(
                f"{author.mention} Źle to robisz! Podany argument jest zły: `{exc}`\n"
            )
            await ctx.send_help(ctx.command)
        elif isinstance(exc, discord.ext.commands.errors.CommandOnCooldown):
            await ctx.send(
                f"{author.mention} Zwolnij kowboju! Ta komenda została użyta {exc.cooldown.per - exc.retry_after:.2f}s temu. Poczekaj chwilę i spróbuj ponownie"
            )
        elif isinstance(exc, commands.MissingRequiredArgument):
            await ctx.send(
                f"{author.mention} Brakuje Ci wymaganego argumentu: {exc.param.name}\n"
            )
            await ctx.send_help(ctx.command)
        elif isinstance(exc, discord.NotFound):
            await ctx.send("Nie znaleziono podanego ID.")
        elif isinstance(exc, discord.Forbidden):
            await ctx.send(f"Jak Ci mam pomóc skoro mi nie pozwalasz!\n`{exc.text}`")
        elif isinstance(exc, commands.CommandInvokeError):
            await ctx.send(
                f"{author.mention} Wystąpił wyjątek podczas użycia komendy `{command}`."
            )
        else:
            if not isinstance(command, str):
                command.reset_cooldown(ctx)
            await ctx.send(
                f"{author.mention} Nieoczekiwany wyjątek wystąpił podczas używania komendy `{command}`."
            )

    async def on_error(self, event_method, *args, **kwargs):
        log.error(f"Error in event: {event_method}")

    async def on_message(self, message):
        if isinstance(message.channel, discord.DMChannel):
            # Ignore direct messages
            return

        await self.process_commands(message)


def run_bot() -> int:
    # Attempt to get current git information
    try:
        commit = check_output(["git", "rev-parse", "HEAD"]).decode("ascii")[:-1]
    except CalledProcessError as e:
        print(f"Checking for git commit failed: {type(e).__name__}: {e}")
        commit = "<unknown>"

    try:
        branch = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode()[
            :-1
        ]
    except CalledProcessError as e:
        print(f"Checking for git branch failed: {type(e).__name__}: {e}")
        branch = "<unknown>"

    bot = Camila(
        (".", "!"), description="Camila, a calendar and task managment Discord bot"
    )
    bot.help_command = commands.DefaultHelpCommand(dm_help=None)
    log.info(f"Starting Camila on commit {commit} on branch {branch}")
    bot.load_cogs()
    try:
        bot.run(config["Secrets"]["BotToken"])
    except KeyboardInterrupt:
        log.warn(f"Received keyboard interrupt. Stopping...")

    return bot.exitcode


if __name__ == "__main__":
    exit(run_bot())
