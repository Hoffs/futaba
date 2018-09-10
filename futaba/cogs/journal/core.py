#
# cogs/journal/core.py
#
# futaba - A Discord Mod bot for the Programming server
# Copyright (c) 2017 Jake Richardson, Ammon Smith, jackylam5
#
# futaba is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

'''
Cog for configuring Futaba journalling output, directing certain kinds
of messages to different logging channels.
'''

import asyncio
import logging

import discord
from discord.ext import commands

from futaba import permissions
from futaba.enums import Reactions
from futaba.journal import ChannelOutputListener, Router

logger = logging.getLogger(__name__)

__all__ = [
    'Journal',
]

class Journal:
    __slots__ = (
        'bot',
        'router',
    )

    def __init__(self, bot):
        self.bot = bot
        self.router = Router()

        logger.info("Loading journal output channels from the database")
        with bot.sql.transaction():
            for guild in bot.guilds:
                bot.sql.journal.get_journal_channels(guild)

        self.router.start(bot.loop)

    @commands.group(name='journal', aliases=['log'])
    async def log(self, ctx):
        ''' Configure channel output for bot journal events. '''

        if ctx.invoked_subcommand is None:
            # TODO send help
            await Reactions.FAIL.add(ctx.message)

    @log.command(name='show', aliases=['display', 'list'])
    @commands.guild_only()
    @permissions.check_mod()
    async def log_show(self, ctx):
        ''' Displays current settings for this guild '''

        outputs = self.bot.sql.journal.get_journal_channels(ctx.guild)
        outputs.sort(key=lambda x: x.channel.name)
        lines = [f'**Current journal outputs for {ctx.guild.name}**']
        attributes = []
        for output in outputs:
            if not output.attributes.recursive:
                attributes.append('exact path')

            lines.append(f'{output.channel.mention} `{output.path}` {", ".join(attributes)}')
            attributes.clear()

        if len(lines) > 1:
            content = '\n'.join(lines)
        else:
            content = f'**No journal outputs for {ctx.guild.name}**'

        await asyncio.gather(
            ctx.send(content=content),
            Reactions.SUCCESS.add(ctx.message),
        )

    @log.command(name='add', aliases=['append', 'extend', 'new'])
    @commands.guild_only()
    @permissions.check_mod()
    async def log_add(self, ctx, channel: discord.TextChannel, path: str, *flags: str):
        '''
        Add a journal logger to the channel for the given path.
        Accepts the optional flags:
            -exact, Don't recursively accept journal events from children.
        '''

        logging.info("Adding journal logger for channel #%s (%d) on path '%s'",
                channel.name, channel.id, path)
        recursive = True

        for flag in flags:
            if flag == '-exact':
                recursive = False
            else:
                await asyncio.gather(
                    Reactions.FAIL.add(ctx.message),
                    ctx.send(content=f'No such flag: `{flag}`')
                )
                return

        logger.debug("Registering route")
        self.router.register(ChannelOutputListener(self.router, path, channel))

        logger.debug("Updating database for channel output")
        with self.bot.sql.transaction():
            if self.bot.sql.journal.has_journal_channel(channel, path):
                self.bot.sql.add_journal_channel(channel, path, recursive)
            else:
                self.bot.sql.update_journal_channel(channel, path, recursive)

        await Reactions.SUCCESS.add(ctx.message)

    @log.command(name='remove', aliases=['rm', 'delete', 'del'])
    @commands.guild_only()
    @permissions.check_mod()
    async def log_remove(self, ctx, channel: discord.TextChannel, path: str):
        '''
        Removes a journal logger for the given path from the channel.
        '''

        logging.info("Removing journal logger for channel #%s (%d) from path '%s'",
                channel.name, channel.id, path)

        with self.bot.sql.transaction():
            self.bot.sql.delete_journal_channel(channel, path)

        await Reactions.SUCCESS.add(ctx.message)
