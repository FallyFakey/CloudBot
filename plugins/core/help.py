import asyncio
import os
import re
from operator import attrgetter

from cloudbot import hook
from cloudbot.util import formatting


@hook.command("help", autohelp=False)
@asyncio.coroutine
def help_command(text, chan, conn, bot, notice, reply, message, has_permission, triggered_prefix):
    """[command] - gives help for [command], or lists all available commands if no command is specified
    :type text: str
    :type conn: cloudbot.client.Client
    :type bot: cloudbot.bot.CloudBot
    """
    if text:
        searching_for = text.lower().strip()
        if not re.match(r'\w+$', searching_for):
            reply("Invalid command name '{}'".format(text))
            return
    else:
        searching_for = None

    if searching_for:
        if searching_for in bot.plugin_manager.commands:
            doc = bot.plugin_manager.commands[searching_for].doc
            if doc:
                reply("{}{} {}".format(triggered_prefix, searching_for, doc))
            else:
                reply("Command {} has no additional documentation.".format(searching_for))
            aliases = bot.plugin_manager.commands[searching_for].aliases
            if len(aliases) > 1:
                reply("Aliases: {}".format(", ".join(a for a in bot.plugin_manager.commands[searching_for].aliases)))
        else:
            reply("Unknown command '{}'".format(searching_for))
    else:
        commands = []

        for plugin in sorted(set(bot.plugin_manager.commands.values()), key=attrgetter("name")):
            # use set to remove duplicate commands (from multiple aliases), and sorted to sort by name

            if plugin.permissions:
                # check permissions
                allowed = False
                for perm in plugin.permissions:
                    if has_permission(perm, notice=False):
                        allowed = True
                        break

                if not allowed:
                    # skip adding this command
                    continue

            # add the command to lines sent
            commands.append(plugin.name)

        # list of lines to send to the user
        lines = formatting.chunk_str("Here's a list of commands you can use: " + ", ".join(commands))
        lines.append("For detailed help, use {}help <command>, without the brackets.".format(triggered_prefix))

        for line in lines:
            if chan[:1] == "#":
                notice(line)
            else:
                # This is an user in this case.
                message(line)


@hook.command
@asyncio.coroutine
def cmdinfo(text, bot, reply):
    """<command> - Gets various information about a command"""
    cmd = text.split()[0].lower().strip()

    if cmd in bot.plugin_manager.commands:
        cmd_hook = bot.plugin_manager.commands[cmd]
    else:
        potentials = []
        for potential_match, plugin in bot.plugin_manager.commands.items():
            if potential_match.startswith(cmd):
                potentials.append((potential_match, plugin))

        if potentials:
            if len(potentials) == 1:
                cmd_hook = potentials[0][1]
            else:
                reply("Possible matches: {}".format(
                    formatting.get_text_list(sorted([command for command, plugin in potentials]))))
                return
        else:
            cmd_hook = None

    if cmd_hook is None:
        reply("Unknown command: '{}'".format(cmd))
        return

    hook_name = cmd_hook.plugin.title + "." + cmd_hook.function_name
    info = "Command: {}, Aliases: [{}], Hook name: {}".format(
        cmd_hook.name, ', '.join(cmd_hook.aliases), hook_name
    )

    if cmd_hook.permissions:
        info += ", Permissions: [{}]".format(', '.join(cmd_hook.permissions))

        reply(info)


@hook.command(permissions=["botcontrol"], autohelp=False)
def generatehelp(conn, bot):
    """- Dumps a list of commands with their help text to the docs directory formatted using markdown."""
    message = "{} Command list\n".format(conn.nick)
    message += "------\n"
    for plugin in sorted(set(bot.plugin_manager.commands.values()), key=attrgetter("name")):
        # use set to remove duplicate commands (from multiple aliases), and sorted to sort by name
        command = plugin.name
        aliases = ""
        doc = bot.plugin_manager.commands[command].doc
        permission = ""
        for perm in plugin.permissions:
            permission += perm + ", "
        permission = permission[:-2]
        for alias in plugin.aliases:
            if alias == command:
                pass
            else:
                aliases += alias + ", "
        aliases = aliases[:-2]
        if doc:
            doc = doc.replace("<", "&lt;").replace(">", "&gt;") \
                .replace("[", "&lt;").replace("]", "&gt;")
            if aliases:
                message += "**{} ({}):** {}\n\n".format(command, aliases, doc)
            else:
                # No aliases so just print the commands
                message += "**{}**: {}\n\n".format(command, doc)
        else:
            message += "**{}**: Command has no documentation.\n\n".format(command)
        if permission:
            message = message[:-2]
            message += " ( *Permission required:* {})\n\n".format(permission)
    # toss the markdown text into a paste
    # out = web.paste(message.encode('utf-8'), ext="md")
    docs = os.path.join(os.path.abspath(os.path.curdir), "docs")
    docs = os.path.join(os.path.join(docs, "user"), "commands.md")
    with open(docs, 'w', encoding="utf-8") as f:
        f.write(message)
    return "Generated help docs to " + docs
