# import telegram

# def send_notification():

#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Simple Bot to reply to Telegram messages. This is built on the API wrapper, see
# echobot2.py to see the same example built on the telegram.ext bot framework.
# This program is dedicated to the public domain under the CC0 license.
import logging
import telegram
import time

from retry import retry
from retry.api import retry_call
from collections import namedtuple
from threading import Thread

from telegram.ext import Updater
from telegram.ext import CommandHandler, MessageHandler, Filters

import telegram
import ccxt
import threading

TOKEN = '409324583:AAHFB2vT4rKuC6rIFk-KSSQas-gZxjzbIko'

MIN_VOL = 0.1
CHAT_ID = 111827564

lock = threading.Lock()
pending = set()
completed = set()

MAPPING = {'btrx': 'bittrex', 'hit': 'hitbtc', 'cryp': 'cryptopia'}


def scan_markets():
    while True:
        with lock:
            pending_copy = set(pending)

        for alert in pending_copy:
            client = getattr(ccxt, alert.exchange)()
            order_book = retry_call(client.fetch_order_book, fargs=[alert.market], tries=3, delay=1)
            alert_price = alert.price
            side = alert.side
            data = order_book['asks'] if side == 'b' else order_book['bids']
            side_sign = 1 if side == 'b' else -1
            total_volume = 0
            for price, qty in data:
                if (price - alert_price) * side_sign > 0:
                    break
                total_volume += price * qty
            if total_volume > MIN_VOL:
                with lock:
                    completed.add(alert)
        time.sleep(1)


def check_completed():
    global completed
    global pending
    bot = telegram.Bot(TOKEN)
    while True:
        with lock:
            for task in completed:
                bot.send_message(chat_id=CHAT_ID, text=repr(task))
            pending = pending.difference(completed)
            completed = set()
        time.sleep(1)


def verify_input(exchange, side):
    if exchange not in MAPPING.keys():
        return 'Exchange is not in the list'
    if side not in ['b', 's']:
        return 'Side is not valid'

def add_alert(bot, update):
    text = update.message.text
    try:
        _, exchange, mkt, price, side = text.split(' ')
    except:
        update.message.reply_text('Wrong number of args')
        return
    exchange = exchange.lower()
    mkt = mkt.upper()
    side = side.lower()
    reason = verify_input(exchange, side)
    if reason:
        update.message.reply_text(reason)
        return
    with lock:
        pending.add(MarketAlert(MAPPING[exchange], mkt, float(price), side))


def show_alerts(bot, update):
    with lock:
        pending_copy = set(pending)
    bot.send_message(chat_id=CHAT_ID, text='Alerts')
    for alert in pending_copy:
        bot.send_message(chat_id=CHAT_ID, text=repr(alert))


def telegram_watcher():
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    add_alert_handler = CommandHandler('add_alert', add_alert)
    show_alerts_handler = CommandHandler('show_alerts', show_alerts)

    dispatcher.add_handler(add_alert_handler)
    dispatcher.add_handler(show_alerts_handler)

    updater.start_polling()


def main():

    scanner_thread = Thread(target=scan_markets)
    scanner_thread.start()
    telegram_thread = Thread(target=telegram_watcher)
    telegram_thread.start()
    completed_thread = Thread(target=check_completed)
    completed_thread.start()

    scanner_thread.join()
    telegram_thread.join()
    completed_thread.join()


class MarketAlert(namedtuple('MarketAlert', ['exchange', 'market',
                                             'price', 'side'])):
    def __repr__(self):
        side = 'less' if self.side == 'b' else 'greater'
        return '%s: price is %s than %s for market %s' % (self.exchange, side,
                                                          self.price, self.market)

    def __hash__(self):
        return hash(repr(self))

    def __eq__(self, other):
        return repr(self) == repr(other)


if __name__ == '__main__':
    main()
