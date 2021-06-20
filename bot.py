import telebot
from telebot import types
import conf
import csv
import sqlite3
import os
from datetime import datetime, timedelta
import pandas as pd
import logging

schedule_out_of_date = False

bot = telebot.TeleBot(conf.TOKEN)

sched_path = os.path.join("sched", "sched.txt")

setback_number = 2
setback = timedelta(hours=setback_number)

days_by_number = {
    5: "saturday",
    6: "sunday"
}

days_list = [
    "weekday",
    "saturday",
    "sunday"
]
weekdays_rus_names_list = {
    "weekday": {
        "nom": "будни",
        "acc": "будни"
    },
    "saturday": {
        "nom": "суббота",
        "acc": "субботу"
    },
    "sunday": {
        "nom": "воскресенье",
        "acc": "воскресенье"
    }
}
places_list = [
    "dub",
    "odi",
    "slav"
]

places_rus_names_list = {
    "dub": {
        "nom": "Дубки",
        "gen": "Дубков"
    },
    "odi": {
        "nom": "Одинцово",
        "gen": "Одинцова"
    },
    "slav": {
        "nom": "Славянка",
        "gen": "Славянки"
    }
}
places_names_list = {
    "дуб": "dub",
    "dub": "dub",
    "оди": "odi",
    "odi": "odi",
    "сла": "slav",
    "бул": "slav",
    "sla": "slav",
    "bou": "slav"
}
weekdays_names_list = {
    "пн": "weekday",
    "понед": "weekday",
    "вт": "weekday",
    "ср": "weekday",
    "чт": "weekday",
    "четв": "weekday",
    "пт": "weekday",
    "пятн": "weekday",
    "сб": "saturday",
    "субб": "saturday",
    "вс": "sunday",
    "воск": "sunday",
    "mo": "weekday",
    "tu": "weekday",
    "we": "weekday",
    "th": "weekday",
    "fr": "weekday",
    "sa": "saturday",
    "su": "sunday",
    "буд": "weekday"
}


def odd(number):
    if number % 2 == 0:
        return False
    return True


def nullize(bus):
    hour = str(int(bus[:bus.find(":")]) % 24)
    min = bus[bus.find(":") + 1:]

    return numify(f"{hour}:{min}")


def denullize(bus):
    hour = bus[:bus.find(":")]
    min = bus[bus.find(":") + 1:]

    if int(hour) < setback_number:
        hour = str(int(hour) + 24)

    return numify(f"{hour}:{min}")


def sort_schedule(schedule):
    for day in days_list:
        for place in places_list:
            schedule[day][place].sort()

            day_buses = []
            night_buses = []
            for i in range(len(schedule[day][place])):
                bus = numify(schedule[day][place][i])

                if int(bus[0]) == 0 and int(bus[1]) < 4:
                    night_buses.append(bus)
                else:
                    day_buses.append(bus)

            schedule[day][place] = day_buses + night_buses


def at_arrival(row):
    for i in range(len(row)):
        if row[i] == "по_прибытию":
            if not odd(i):
                logging.error(f"Something wrong with «по прибытию»! This row has «по прибытию» in even columns: {row}.")
            else:
                row[i] = f"{row[i - 1]} (по приб.)"


def update_schedule(sched_path):
    schedule = {}
    for day in days_list:
        schedule[day] = {}
        for place in places_list:
            schedule[day][place] = []

    with open(sched_path, encoding="utf-8-sig") as f:
        reader_machine = csv.reader(f, delimiter=" ")
        day = "weekday"
        for row in reader_machine:
            if row:
                if row[0].startswith("#"):

                    if row[0] == "#суббота":
                        day = "saturday"
                    elif row[0] == "#воскресенье":
                        day = "sunday"

                else:

                    at_arrival(row)

                    for i in range(int(len(row))):

                        if row[i] == "----":
                            continue

                        if not odd(i):
                            place = "dub"
                        else:
                            place = "odi"
                        if row[i].endswith("**"):
                            place = "slav"
                            row[i] = row[i][:row[i].find("**")]
                        elif row[i].endswith("*"):
                            row[i] = row[i][:row[i].find("*")]
                            row[i] = f"{row[i]} (до {places_rus_names_list['slav']['nom'][:4]}.)"

                        row[i] = denullize(numify(row[i]))

                        schedule[day][place].append(row[i])

    sort_schedule(schedule)

    return schedule


def can_be_hour(number):
    try:
        number = int(number)
    except ValueError:
        return False

    if number < 0:
        return False
    if number > 23:
        return False

    return True


def can_be_time(bus):
    hour = bus[:bus.find(":")]
    min = bus[bus.find(":") + 1:]

    if not can_be_hour(hour):
        return False

    try:
        min = int(min)
    except ValueError:
        return False

    if min < 0:
        return False
    if min > 59:
        return False

    return True


def numify(bus):
    hour = bus[:bus.find(":")]
    min = bus[bus.find(":") + 1:]

    try:
        hour = str(int(hour))
        min_cleaned = min
        if min_cleaned.find("(") > -1:
            min_cleaned = min_cleaned[:min_cleaned.find(" (")]
        min_cleaned = str(int(min_cleaned))
    except ValueError:
        logging.error(f"Something wrong with time: {bus}!")

    while len(hour) < 2:
        hour = f"0{hour}"
    while len(min) < 2:
        min = f"0{min}"
    return f"{hour}:{min}"


def define_time():
    moment = datetime.now() - setback
    hour = moment.hour + setback_number
    time = numify(f"{hour}:{moment.minute}")

    if moment.weekday() in days_by_number:
        day_of_week = days_by_number[moment.weekday()]
    else:
        day_of_week = "weekday"

    return time, day_of_week


def code_place(message):
    if message.lower() == places_rus_names_list["odi"]["nom"].lower():
        return "odi"
    elif message.lower() == places_rus_names_list["dub"]["nom"].lower():
        return "dub"
    return "slav"


def place_choice_markup():
    markup = types.ReplyKeyboardMarkup(row_width=3)
    btn = {}
    btn["dub"] = types.KeyboardButton(places_rus_names_list["dub"]["nom"])
    btn["odi"] = types.KeyboardButton(places_rus_names_list["odi"]["nom"])
    btn["slav"] = types.KeyboardButton(places_rus_names_list["slav"]["nom"])
    markup.row(btn["dub"], btn["odi"], btn["slav"])
    return markup


@bot.message_handler(commands=["hello", "help"])
def hello(message):
    greetings = [
        "Привет! Я буду присылать тебе актуальное расписание автобусов от и до Дубковского общежития московской Вышки.",
        "Используй команды /next или /now, чтобы получить список ближайших автобусов.",
        "Ещё ты можешь написать простой запрос, состоящий из времени, дня недели и места отправления, типа "
        "`суббота дубки 14:00`, `оди 8 чт` или `славянка`, и я покажу расписание на нужное время и место. "
        "Если время или день недели не указаны, пришлю ближайшие рейсы от этого места.",
        "Указывай ночное время по предыдущему дню. Например, по запросу `friday 00:20 odi` "
        "пришлю рейсы от Одинцова в ночь с пятницы на субботу.",
        "Указывай время в 24-часовом формате. На запрос `чт 7 слав` покажу расписание автобусов "
        "от Славянского бульвара не на 19:00, а на 7 утра.",
        "Утренние рейсы от Одинцова «по прибытию» указаны по времени отправки от Дубков, с припиской. "
        "Например, рейс `08:07 (по приб.)` отправляется в Одинцово в 08:07, через некоторое время прибывает "
        "в Одинцово и по прибытию отъезжает обратно в Дубки.",
        "Попробуй найти ближайший автобус: нажми /next :)"
    ]
    for greeting in greetings:
        bot.send_message(message.chat.id, greeting, parse_mode="Markdown")


@bot.message_handler(commands=["next", "now"])
def get_next_bus_place(message, weekday=False, time=False):
    markup = place_choice_markup()
    msg = bot.send_message(message.chat.id, "Откуда едем?", reply_markup=markup, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_set_time, weekday=weekday, time=time)


@bot.message_handler(content_types=["text"])
def process_set_time(message, place=False, weekday=False, time=False):

    pieces = message.text.split(" ")

    if len(pieces) > 20 or len(message.text) > 60:
        logging.error("Request too big!")
        bot.send_message(message.chat.id, "Лев Николаевич, не пишите больше сюда, пожалуйста. "
                                          "Здесь нужны короткие и ёмкие запросы. Я понимаю, у нас тут Дубки, "
                                          "вам это близко… Но надо знать меру.")
        return

    now, today = define_time()
    now_requested = False

    bad_pieces = []

    for piece in pieces:

        if piece.lower() in ["сейчас", "now", "next"]:
            now_requested = True
            time = now
            weekday = today
            continue

        if not place:
            for place_name in places_names_list:  # defining place
                if piece.lower().startswith(place_name):
                    place = places_names_list[place_name]
                    break
            if place:
                continue

        if not weekday:
            for weekday_name in weekdays_names_list:  # defining weekday
                if piece.startswith(weekday_name):
                    weekday = weekdays_names_list[weekday_name]
                    break
            if weekday:
                continue

        if not time:
            if ":" in piece or "." in piece:  # defining time
                if not can_be_time(piece):
                    logging.error(f"Such time doesn't exist: {piece}!")
                    time = "Вот в такое время автобусов точно не бывает."
                    continue
                time = denullize(numify(piece))
                continue
            elif can_be_hour(piece):
                time = denullize(numify(f"{piece}:00"))
            else:
                time = False
            if time:
                continue

        bad_pieces.append(piece)

    reply = ""

    if now_requested and not place:
        message.text = "/next"
        get_next_bus_place(message)
    else:
        if not place:
            logging.error(f"Place was not given: {message.text}!")
            place = "Place was not given"
        else:
            if not weekday:
                weekday = today
            if not time:
                time = now

            if bad_pieces:
                reply = reply + f"Я не знаю, что такое `{', '.join(bad_pieces)}` :(\n"
                logging.error(f"Unknown tokens in the message: {', '.join(bad_pieces)}!")
            if place:
                if (not weekday) and (not time):
                    reply = reply + f"Ближайшие рейсы от {places_rus_names_list[place]['gen']}:"
                elif not weekday:
                    reply = reply + f"Рейсы от {places_rus_names_list[place]['gen']} на {time} сегодня:"
                else:
                    reply = reply + f"Рейсы от {places_rus_names_list[place]['gen']} " \
                                    f"на {time} в {weekdays_rus_names_list[weekday]['acc']}:"

        get_next_bus(message, place, weekday, time, reply)


def markdownize_suggested(suggested_buses):
    suggested_buses = " | ".join(suggested_buses)
    if suggested_buses.find('|') > -1:
        return f"*{suggested_buses[:suggested_buses.find('|')]}*`{suggested_buses[suggested_buses.find('|'):]}`"
    return f"*{suggested_buses}*"


def get_next_bus(message, place=False, weekday=False, time=False, reply=False):
    if not place:
        place = code_place(message.text)
    if not weekday:
        weekday = define_time()[1]
    if not time:
        time = define_time()[0]

    if not can_be_time(time):
        bot.send_message(message.chat.id, time)
        return

    if not place in places_list:
        get_next_bus_place(message, weekday, time)

    else:
        suggested_buses = []

        for bus in schedule[weekday][place]:
            if bus > time:
                suggested_buses.append(nullize(bus))
            if len(suggested_buses) > 4:
                break

        if schedule_out_of_date:
            bot.send_message(message.chat.id, "*Осторожно! Это расписание может быть устаревшим.*\n"
                             "Свежее расписание смотрите [в группе ВКонтакте](https://vk.com/dubki).",
                             parse_mode="Markdown")

        if not schedule[weekday][place]:
            bot.send_message(message.chat.id, f"К сожалению, в {weekdays_rus_names_list[weekday]['acc']} "
                                              f"от {places_rus_names_list[place]['gen']} автобусы не идут.",
                             reply_markup=types.ReplyKeyboardRemove())
            return
        if not suggested_buses:
            bot.send_message(message.chat.id, f"К сожалению, в это время"
                                              f"от {places_rus_names_list[place]['gen']} автобусы не идут.",
                             reply_markup=types.ReplyKeyboardRemove())
            return

        if not reply:
            logging.error(f"Something wrong with reply message: {reply}. Original message: {message.text}")
        else:
            bot.send_message(message.chat.id, reply, parse_mode="Markdown")

        bot.send_message(message.chat.id, markdownize_suggested(suggested_buses),
                         reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")


if __name__ == '__main__':
    schedule = update_schedule(sched_path)
    print(schedule)

    bot.polling(none_stop=True)

"""
TODO:
- database support
- report a problem
- automatic location definer
"""
