import telebot
from telebot import types
import conf
import csv
import sqlite3
import os
from datetime import datetime, timedelta
import logging
import time

schedule_out_of_date = False  # если True, то будет выдавать предупреждение пользователю, что расписание устарело
update_necessary = False  # если True, то загрузит расписание из sched_path (txt-файла), а не из базы данных

bot = telebot.TeleBot(conf.TOKEN)

logging.basicConfig(format=u"[LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s", level="INFO",
                    filename="log.txt", encoding="utf-8")
logging.basicConfig(format=u"[LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s", level="ERROR",
                    filename="log.txt", encoding="utf-8")
logging.basicConfig(format=u"[LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s",
                    level="WARNING", filename="log.txt", encoding="utf-8")

sched_path = os.path.join("sched", "sched.txt")  # путь к txt-файлу с расписанием
database_path = os.path.join("sched", "sched.db")  # путь к базе данных с расписанием
pdf_path = os.path.join("sched", "sched.pdf")  # путь к pdf-файлу с расписанием
users_path = os.path.join("other", "users.db")  # путь к базе данных со списком пользователей

setback_number = 2  # количество часов, которое проходит после полуночи, прежде чем бот считает, что наступил
setback = timedelta(hours=setback_number)  # новый день

amount_of_suggested_buses = 4

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
    if bus.find(":") < 0:
        return bus

    hour = str(int(bus[:bus.find(":")]) % 24)
    minutes = bus[bus.find(":") + 1:]

    return numify(f"{hour}:{minutes}")


def denullize(bus):
    if bus.find(":") < 0:
        return bus

    hour = bus[:bus.find(":")]
    minutes = bus[bus.find(":") + 1:]

    if int(hour) < setback_number:
        hour = str(int(hour) + 24)

    return numify(f"{hour}:{minutes}")


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
                logging.error(f"Some row has «по прибытию» in even columns: {row}.")
            else:
                row[i] = f"{row[i - 1]} (по приб.)"


def get_database():
    schedule = {}

    con = sqlite3.connect(database_path)
    cur = con.cursor()

    cur.execute("""SELECT * FROM schedule""")

    for i in range(1, len(cur.fetchall()) + 1):
        cur.execute("SELECT * FROM schedule where bus_id = ?", (i,))
        row = cur.fetchall()[0]

        if not row[1] in schedule:
            schedule[row[1]] = {}
        if not row[2] in schedule[row[1]]:
            schedule[row[1]][row[2]] = []
        schedule[row[1]][row[2]].append(row[3])
    return schedule


def update_database(schedule):
    restruct = []

    i = 0
    for day in schedule:
        for place in schedule[day]:
            for bus in schedule[day][place]:
                i = i + 1
                restruct.append((i, day, place, bus))

    con = sqlite3.connect(database_path)
    cur = con.cursor()

    cur.execute("DROP TABLE IF EXISTS schedule")
    cur.execute("""
    CREATE TABLE schedule (
        bus_id INT,
        day TEXT, 
        place TEXT, 
        bus TEXT,
        PRIMARY KEY (bus_id)
    )
    """)

    cur.executemany("INSERT INTO schedule VALUES (?, ?, ?, ?)", restruct)
    con.commit()


def update_schedule():
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
    update_database(schedule)
    return schedule


def get_users():
    con = sqlite3.connect(users_path)
    cur = con.cursor()
    cur.execute("""SELECT user_id FROM users""")

    users = []
    for row in cur.fetchall():
        users.append(row[0])

    return users


def update_users(user_id, delete=False):
    con = sqlite3.connect(users_path)
    cur = con.cursor()

    cur.execute("SELECT user_id FROM users where user_id = ?", (user_id,))
    if not delete:
        if not cur.fetchall():
            cur.execute("INSERT INTO users VALUES (?)", (user_id,))
            con.commit()
            logging.info(f"New user: {user_id}.")

    else:
        if cur.fetchall():
            cur.execute("DELETE FROM users WHERE user_id = (?)", (user_id,))
            con.commit()
            logging.info(f"User {user_id} has blocked the bot and has been deleted from the database.")


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
    minutes = bus[bus.find(":") + 1:]

    if not can_be_hour(hour):
        return False

    try:
        minutes = int(minutes)
    except ValueError:
        return False

    if minutes < 0:
        return False
    if minutes > 59:
        return False

    return True


def numify(bus):
    hour = bus[:bus.find(":")]
    minutes = bus[bus.find(":") + 1:]

    try:
        hour = str(int(hour))
        min_cleaned = minutes
        if min_cleaned.find("(") > -1:
            min_cleaned = min_cleaned[:min_cleaned.find(" (")]
        str(int(min_cleaned))
    except ValueError:
        logging.warning(f"Something wrong with time: '{bus}'!")

    while len(hour) < 2:
        hour = f"0{hour}"
    while len(minutes) < 2:
        minutes = f"0{minutes}"
    return f"{hour}:{minutes}"


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
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    btn = {"dub": types.KeyboardButton(places_rus_names_list["dub"]["nom"]),
           "odi": types.KeyboardButton(places_rus_names_list["odi"]["nom"]),
           "slav": types.KeyboardButton(places_rus_names_list["slav"]["nom"])}
    markup.row(btn["dub"], btn["odi"], btn["slav"])
    return markup


def send(user_id, text, parse_mode=None, reply_markup=None):
    try:
        message = bot.send_message(user_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        return message
    except telebot.apihelper.ApiException:
        update_users(user_id=user_id, delete=True)
        return False
    except (ConnectionAbortedError, ConnectionResetError, ConnectionRefusedError, ConnectionError):
        logging.error("ConnectionError, message delayed")
        time.sleep(1)
        msg = send(user_id, text, parse_mode, reply_markup)
        if not msg:
            return False


@bot.message_handler(commands=["hello", "start", "help"])
def hello(message):
    greetings = [
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
        "Если хочешь получить .pdf-файл с расписанием, просто напиши /pdf.",
        "Если я веду себя неадекватно или у тебя есть вопросы или предложения, не стесняйся использовать команду "
        "/report, чтобы сообщить о проблеме."
    ]
    if message.text in ["/hello", "/start"]:
        send(message.chat.id, "Привет! Я буду присылать тебе актуальное расписание автобусов от и до "
                                "Дубковского общежития московской Вышки.")
    for greeting in greetings:
        send(message.chat.id, greeting, parse_mode="Markdown")
    if message.text in ["/hello", "/start"]:
        send(message.chat.id, "Попробуй найти ближайший автобус: нажми /next :)")


@bot.message_handler(commands=["report"])
def report(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    a = types.KeyboardButton("Бот")
    b = types.KeyboardButton("Расписание")
    c = types.KeyboardButton("Другое")
    markup.row(a, b, c)

    msg = send(message.chat.id, "С чем именно проблема?", reply_markup=markup, parse_mode="Markdown")
    if msg:
        bot.register_next_step_handler(msg, write_report)


def write_report(message):
    topic = message.text

    msg = send(message.chat.id, "Опиши проблему сообщением.", reply_markup=types.ReplyKeyboardRemove())
    if msg:
        bot.register_next_step_handler(msg, send_report, topic)


def send_report(message, topic):
    send(conf.DEVELOPER_ID, f"REPORT #report #{topic}. Отвечайте с помощью /answer", parse_mode="Markdown")
    bot.forward_message(conf.DEVELOPER_ID, message.chat.id, message.message_id)
    logging.info(f"Report: #{topic} '{message.text}'! (from user {message.chat.id}, message {message.message_id})")

    send(message.chat.id, "Спасибо! Посмотрю, что можно сделать, подумаю и постараюсь ответить.")


@bot.message_handler(commands=["answer"])
def answer_report(message):
    if message.chat.id != conf.DEVELOPER_ID:
        send(message.chat.id, "Эта команда доступна только разработчикам.")
        return

    msg = send(message.chat.id, "На какое сообщение и как ответить?")
    if msg:
        bot.register_next_step_handler(msg, write_answer_report)


def write_answer_report(reply):
    if hasattr(reply.reply_to_message, "text"):
        if hasattr(reply.reply_to_message, "forward_from") and reply.reply_to_message.forward_from:
            report_message = reply.reply_to_message
        else:
            logging.error("Your answer to a report has no 'reply_to_message.forward_from' attribute.")
            send(reply.chat.id, f"Нужно отправить ответ на пересланное сообщение.")
            return
    else:
        logging.error("Your answer to a report has no 'reply_to_message' attribute.")
        send(reply.chat.id, f"Нужно отправить ответ на пересланное сообщение.")
        return

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    a = types.KeyboardButton("Да")
    b = types.KeyboardButton("Нет")
    markup.row(a, b)

    confirmation = send(reply.chat.id, "Точно?", reply_markup=markup)
    bot.register_next_step_handler(confirmation, confirm_answer_report, reply, report_message)


def confirm_answer_report(confirmation, reply, report_message):
    if confirmation.text == "Да":
        send(report_message.forward_from.id, f"Помнится, ты мне написал(а) следующее:\n{report_message.text}")
        msg = send(report_message.forward_from.id, f"Так вот, отвечаю:\n{reply.text}")
        if not msg:
            return

        send(reply.chat.id, "Ответ отправлен.", reply_markup=types.ReplyKeyboardRemove())
        logging.info(f"Answer: '{reply.text}' (to report {report_message.message_id} "
                     f"from user {report_message.chat.id})")
    else:
        return


@bot.message_handler(commands=["announce"])
def announce(message):
    if message.chat.id != conf.DEVELOPER_ID:
        send(message.chat.id, "Эта команда доступна только разработчикам.")
        return

    msg = send(message.chat.id, "Какое объявление отправить всем пользователям?")
    if msg:
        bot.register_next_step_handler(msg, write_announcement)


def write_announcement(announcement):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    a = types.KeyboardButton("Да")
    b = types.KeyboardButton("Нет")
    markup.row(a, b)

    confirmation = send(announcement.chat.id, "Точно?", reply_markup=markup)
    if confirmation:
        bot.register_next_step_handler(confirmation, confirm_announcement, announcement)


def confirm_announcement(confirmation, announcement):
    if confirmation.text == "Да":
        users = get_users()

        for user_id in users:
            send(user_id, announcement.text)
        send(announcement.chat.id, f"Объявление отправлено {len(users)} пользователям.",
                         reply_markup=types.ReplyKeyboardRemove())
    else:
        return


@bot.message_handler(commands=["pdf"])
def send_pdf(message):
    try:
        with open(pdf_path, "rb") as f:
            bot.send_document(message.chat.id, f)
    except telebot.apihelper.ApiException:
        update_users(user_id=message.chat.id, delete=True)


@bot.message_handler(commands=["next", "now"])
def get_next_bus_place(message, day=False, time=False):
    markup = place_choice_markup()
    try:
        msg = send(message.chat.id, "Откуда едем?", reply_markup=markup, parse_mode="Markdown")
        if msg:
            bot.register_next_step_handler(msg, process_set_time, day=day, time=time)
    except telebot.apihelper.ApiException:
        update_users(user_id=message.chat.id, delete=True)


@bot.message_handler(content_types=["text"])
def process_set_time(message, place=False, day=False, time=False):
    pieces = message.text.split(" ")

    if len(pieces) > 20 or len(message.text) > 60:
        logging.info(f"Request too big! (from user {message.chat.id})")
        msg = send(message.chat.id, "Лев Николаевич, не пишите больше сюда, пожалуйста. "
                                    "Здесь нужны короткие и ёмкие запросы. Я понимаю, у нас тут Дубки, "
                                    "вам это близко… Но надо знать меру.")
        if not msg:
            return

    now, today = define_time()
    now_requested = False

    bad_pieces = []

    for piece in pieces:

        if piece.lower() in ["сейчас", "now", "next", "/now", "/next"]:
            now_requested = True
            time = now
            day = today
            continue

        if piece.lower() in ["завтра", "tomorrow", "послезавтра"]:
            if piece.lower() == "послезавтра":
                tomorrow = (datetime.now().weekday() + 2) % 7
            else:
                tomorrow = (datetime.now().weekday() + 1) % 7
            if tomorrow in days_by_number:
                day = days_by_number[tomorrow]
            else:
                day = "weekday"
            continue

        if not place:
            for place_name in places_names_list:  # defining place
                if piece.lower().startswith(place_name):
                    place = places_names_list[place_name]
                    break
            if place:
                continue

        if not day:
            for weekday_name in weekdays_names_list:  # defining day of the week
                if piece.startswith(weekday_name):
                    day = weekdays_names_list[weekday_name]
                    break
            if day:
                continue

        if not time:
            if ":" in piece or "." in piece:  # defining time
                if not can_be_time(piece):
                    logging.info(f"Such time doesn't exist: '{piece}'! (from user {message.chat.id})")
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

    if now_requested and not place:
        message.text = "/next"
        get_next_bus_place(message)
    else:

        reply = ""

        if not place:
            logging.info(f"Place was not given: '{message.text}'! (from user {message.chat.id})")
            place = "Place was not given"
        else:

            if not day:
                day = today
            if not time:
                time = now

            if bad_pieces:
                reply = reply + f"Я не знаю, что такое `{', '.join(bad_pieces)}` :(\n"
                logging.info(f"Unknown tokens in the message: '{', '.join(bad_pieces)}'! (from user {message.chat.id})")

            if place:
                if day == today and time == now:
                    reply = reply + f"Ближайшие рейсы от {places_rus_names_list[place]['gen']}:"
                else:
                    reply = reply + f"Рейсы от {places_rus_names_list[place]['gen']} " \
                                    f"на {nullize(time)} в {weekdays_rus_names_list[day]['acc']}:"

        get_next_bus(message, place, day, time, reply)


def markdownize_suggested(suggested_buses):
    suggested_buses = " | ".join(suggested_buses)
    x = suggested_buses.find('|')
    if x > -1:
        return f"*{suggested_buses[:x]}*`{suggested_buses[x:]}`"
    return f"*{suggested_buses}*"


def get_next_bus(message, place=False, day=False, time=False, reply=False):
    if not place:
        place = code_place(message.text)
    if not day:
        day = define_time()[1]
    if not time:
        time = define_time()[0]

    if not can_be_time(nullize(time)):
        msg = send(message.chat.id, time)
        if not msg:
            return

    if place not in places_list:
        get_next_bus_place(message, day, time)

    else:
        suggested_buses = []

        for bus in schedule[day][place]:
            if bus > time:
                suggested_buses.append(nullize(bus))
            if len(suggested_buses) > amount_of_suggested_buses - 1:
                break

        if schedule_out_of_date:
            msg = send(message.chat.id, "*Осторожно! Это расписание может быть устаревшим.*\nСвежее "
                                                  "расписание смотрите [в группе ВКонтакте](https://vk.com/dubki).",
                                 parse_mode="Markdown")
            if not msg:
                return

        if not schedule[day][place]:
            msg = send(message.chat.id, f"К сожалению, в {weekdays_rus_names_list[day]['acc']} "
                                        f"от {places_rus_names_list[place]['gen']} автобусы не идут.",
                       reply_markup=types.ReplyKeyboardRemove())
            if not msg:
                return
        if not suggested_buses:
            msg = send(message.chat.id, f"К сожалению, в это время в {weekdays_rus_names_list[day]['acc']} "
                                        f"от {places_rus_names_list[place]['gen']} автобусы не идут.",
                       reply_markup=types.ReplyKeyboardRemove())
            if not msg:
                return

        if not reply:
            logging.warning(f"Something wrong with reply message: '{reply}'. Original message: '{message.text}'.")
        else:
            send(message.chat.id, reply, parse_mode="Markdown")
        send(message.chat.id, markdownize_suggested(suggested_buses), reply_markup=types.ReplyKeyboardRemove(),
             parse_mode="Markdown")


@bot.message_handler(func=lambda message: True, content_types=["audio", "document", "photo", "sticker", "video",
                                                               "video_note", "voice", "location", "contact"])
def handle_types(message):
    send(message.chat.id, "Увы, пока что я не знаю, как на такое реагировать.",
         reply_markup=types.ReplyKeyboardRemove())


if __name__ == "__main__":
    if update_necessary:
        schedule = update_schedule()
    else:
        schedule = get_database()
    print(schedule)
    bot.polling(none_stop=True)
