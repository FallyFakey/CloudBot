import re
import string
from collections import defaultdict

from sqlalchemy import Table, Column, String, PrimaryKeyConstraint

from cloudbot import hook
from cloudbot.util import database, colors, web
from cloudbot.util.formatting import gen_markdown_table

# below is the default factoid in every channel you can modify it however you like
default_dict = {}

re_lineends = re.compile(r'[\r\n]*')

FACTOID_CHAR = "?"  # TODO: config

table = Table(
    "factoids",
    database.metadata,
    Column("word", String(25)),
    Column("data", String(500)),
    Column("nick", String(25)),
    Column("chan", String(65)),
    PrimaryKeyConstraint('word', 'chan')
)


@hook.on_start()
def load_cache(db):
    """
    :type db: sqlalchemy.orm.Session
    """
    global factoid_cache
    factoid_cache = defaultdict(lambda: default_dict)
    for row in db.execute(table.select()):
        # assign variables
        chan = row["chan"]
        word = row["word"]
        data = row["data"]
        if chan not in factoid_cache:
            factoid_cache.update({chan: {word: data}})
        elif word not in factoid_cache[chan]:
            factoid_cache[chan].update({word: data})
        else:
            factoid_cache[chan][word] = data


def add_factoid(db, word, chan, data, nick):
    """
    :type db: sqlalchemy.orm.Session
    :type word: str
    :type data: str
    :type nick: str
    """
    if word in factoid_cache[chan]:
        # if we have a set value, update
        db.execute(table.update().values(data=data, nick=nick, chan=chan).where(table.c.chan == chan).where(
            table.c.word == word))
        db.commit()
    else:
        # otherwise, insert
        db.execute(table.insert().values(word=word, data=data, nick=nick, chan=chan))
        db.commit()
    load_cache(db)


def del_factoid(db, chan, word):
    """
    :type db: sqlalchemy.orm.Session
    :type word: str
    """
    db.execute(table.delete().where(table.c.word == word).where(table.c.chan == chan))
    db.commit()
    load_cache(db)


@hook.command("r", "remember", permissions=["op", "chanop"])
def remember(text, nick, db, chan, reply):
    """<word> [+]<data> - remembers <data> with <word> - add + to <data> to append. If the input starts with <act> the message will be sent as an action. If <user> in in the message it will be replaced by input arguments when command is called."""
    global factoid_cache
    try:
        word, data = text.split(None, 1)
    except ValueError:
        return remember.__doc__

    word = word.lower()
    try:
        old_data = factoid_cache[chan][word]
    except LookupError:
        old_data = None

    if data.startswith('+') and old_data:
        # remove + symbol
        new_data = data[1:]
        # append new_data to the old_data
        if len(new_data) > 1 and new_data[1] in (string.punctuation + ' '):
            data = old_data + new_data
        else:
            data = old_data + ' ' + new_data
        reply("Appending \x02{}\x02 to \x02{}\x02".format(new_data, old_data))
    else:
        reply('Remembering \x02{0}\x02 for \x02{1}\x02. Type {2}{1} to see it.'.format(data, word, FACTOID_CHAR))
        if old_data:
            reply('Previous data was \x02{}\x02'.format(old_data))

    add_factoid(db, word, chan, data, nick)


@hook.command("f", "forget", permissions=["op", "chanop"])
def forget(text, chan, db, reply):
    """<word> - forgets previously remembered <word>"""
    global factoid_cache
    data = factoid_cache[chan][text.lower()]

    if data:
        del_factoid(db, chan, text)
        reply('"{}" has been forgotten.'.format(data.replace('`', "'")))
        return
    else:
        reply("I don't know that factoid.")
        return


@hook.command()
def info(text, chan, reply):
    """<factoid> - shows the source of a factoid"""

    text = text.strip().lower()

    if text in factoid_cache[chan]:
        reply(factoid_cache[chan][text])
    else:
        reply("Unknown Factoid.")


factoid_re = re.compile(r'^{} ?(.+)'.format(re.escape(FACTOID_CHAR)), re.I)


@hook.regex(factoid_re)
def factoid(content, match, chan, message, action):
    """<word> - shows what data is associated with <word>"""
    arg1 = ""
    if len(content.split()) >= 2:
        arg1 = content.split()[1]
    # split up the input
    split = match.group(1).strip().split(" ")
    factoid_id = split[0].lower()

    if factoid_id in factoid_cache[chan]:
        data = factoid_cache[chan][factoid_id]
        result = data

        # factoid post-processors
        result = colors.parse(result)
        if arg1:
            result = result.replace("<user>", arg1)
        if result.startswith("<act>"):
            result = result[5:].strip()
            action(result)
        else:
            message(result)


@hook.command("listfacts", autohelp=False)
def listfactoids(reply, chan):
    """- lists all available factoids"""
    reply_text = []
    reply_text_length = 0
    for word in sorted(factoid_cache[chan].keys()):
        added_length = len(word) + 2
        if reply_text_length + added_length > 400:
            reply(", ".join(reply_text))
            reply_text = []
            reply_text_length = 0
        else:
            reply_text.append(word)
            reply_text_length += added_length
    reply(", ".join(reply_text))


@hook.command("listdetailedfacts", autohelp=False)
def listdetailedfactoids(chan):
    """- lists all available factoids with their respective data"""
    headers = ("Command", "Output")
    data = [(FACTOID_CHAR + fact[0], fact[1]) for fact in sorted(factoid_cache[chan].items())]
    table = gen_markdown_table(headers, data).encode('UTF-8')
    return web.paste(table, "md", "hastebin")
