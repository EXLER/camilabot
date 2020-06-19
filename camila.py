#!/usr/bin/env python3

import os
import configparser
from datetime import datetime
from subprocess import check_output, CalledProcessError
from traceback import format_exc

import discord
from discord.ext import commands

import utils.log

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
        self.channel_config = configparser.ConfigParser()
        self.channel_config.read("channels.ini", encoding="utf-8")

        self.roles = {
            "MITK Core": None,
            "MITK Utils": None,
            "Roboty": None,
            "Omnibus": None,
        }

        self.channels = {
            "syf": None,
            "obrazki": None,
            "granie": None,
            "uczelnia": None,
            "bot": None,
        }

        self.failed_cogs = []
        self.exitcode = 0

    def add_cog(self, cog):
        super().add_cog(cog)
        utils.log.info(f"Cog loaded: {cog.qualified_name}")

    def load_cogs(self):
        for extension in cogs:
            try:
                self.load_extension(extension)
            except BaseException as e:
                utils.log.warn(f"{extension} failed to load.")
                self.failed_cogs.append([extension, type(e).__name__, e])

    def load_channels(self):
        if not self.channel_config.has_section("Channels"):
            self.channel_config.add_section("Channels")

        for n in self.channels:
            if n in self.channel_config.options("Channels"):
                self.channels[n] = self.guild.get_channel(
                    self.channel_config.getint("Channels", n)
                )
            else:
                self.channels[n] = discord.utils.get(self.guild.text_channels, name=n)
                if not self.channels[n]:
                    utils.log.warn(f"Failed to find channel: {n}")
                    continue
                self.channel_config["Channels"][n] = str(self.channels[n].id)
                with open("channels.ini", "w", encoding="utf-8") as f:
                    self.channel_config.write(f)

    def load_roles(self):
        for n in self.roles.keys():
            self.roles[n] = discord.utils.get(self.guild.roles, name=n)
            if not self.roles[n]:
                utils.log.warn(f"Failed to find role: {n}")

    async def on_ready(self):
        self.guild = self.guilds[0]

        self.load_channels()
        self.load_roles()

        startup_message = f"{self.user.name} has started on server '{self.guild}' with {self.guild.member_count} members!"
        if len(self.failed_cogs) != 0:
            startup_message += "\n\nAddons failed to load:\n"
            for fail in self.failed_cogs:
                startup_message += "\n{}: `{}: {}`".format(*fail)
        utils.log.info(startup_message)
        await self.channels["bot"].send(startup_message)

    async def on_error(self, event_method, *args, **kwargs):
        await self.channels["bot"].send(f"Error in event: {event_method}")


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
    utils.log.info(f"Starting Camila on commit {commit} on branch {branch}")
    bot.load_cogs()
    bot.run(config["Secrets"]["BotToken"])

    return bot.exitcode


if __name__ == "__main__":
    exit(run_bot())
