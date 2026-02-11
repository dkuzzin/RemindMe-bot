import telebot
import dateparser
import datetime
import json
import threading
import time

from telebot import types
from telebot.apihelper import ApiException

tmp = {}
bot = telebot.TeleBot('')


def save_reminds(reminds):
    with open("reminds.json", "r+", encoding="utf-8") as file:
        file.seek(0)
        json.dump(reminds, file, indent=4, ensure_ascii=False)
        file.truncate()

def remind_checker():
    last_cleanup_month = None
    while True:
        with open("reminds.json", "r+", encoding="utf-8") as file:
            changed = False
            reminds = json.load(file)
            now = datetime.datetime.now()

            for user_id, user_rem in list(reminds.items()):
                for rem in user_rem:
                    remind_time = datetime.datetime.fromisoformat(rem["remind time"])
                    if not rem["is completed"] and remind_time <= now:
                        try:
                            bot.send_message(user_id, f"⏰Ваше напоминание\n{rem['text']}, ({remind_time.strftime('%d.%m.%Y %H:%M')})")
                            rem["is completed"] = True
                            changed = True
                        except ApiException as e:
                            if "bot was blocked by the user" in str(e) or "kicked from the group chat" in str(e):
                                print(f"Пользователь {user_id} недоступен, удаляю его напоминания")
                                reminds.pop(str(user_id), None)
                                changed = True
                            else:
                                print(f"Ошибка Telegram API: {e}")

            if now.day == 1 and last_cleanup_month != now.month:
                changed = True
                last_cleanup_month = now.month
                month_ago = now - datetime.timedelta(days=31)

                for user_id in list(reminds.keys()):
                    items = [
                        rem for rem in reminds[user_id]
                        if (not rem.get("is completed")) or
                           (datetime.datetime.fromisoformat(rem["remind time"]) > month_ago)
                    ]
                    if items:
                        reminds[user_id] = items
                    else:
                        del reminds[user_id]
            if changed:
                save_reminds(reminds)
        time.sleep(30)
threading.Thread(target=remind_checker, daemon=True).start()





def get_main_menu():
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("➕Создать напоминание")
    btn2 = types.KeyboardButton("📃Список")
    menu.add(btn1, btn2)
    return menu
def get_cancel_menu():
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancelBtn = types.KeyboardButton("❌ Отмена")
    menu.add(cancelBtn)
    return menu

def get_numbers(count):
    menu = types.InlineKeyboardMarkup()
    for i in range(1, count+1):
        menu.add(types.InlineKeyboardButton(f"{i}", callback_data=f"num:{i}"))
    return menu

def get_edit_menu(number, reminds, user_id):
    menu = types.InlineKeyboardMarkup()

    if reminds[user_id][number]["is completed"]:
        btn1 = types.InlineKeyboardButton("🔁 Напомнить еще раз", callback_data=f"uncomplete:{number}")
        btn2 = types.InlineKeyboardButton("🗑️Удалить", callback_data=f"delete:{number}")
        menu.add(btn1, btn2)
    else:
        btn1 = types.InlineKeyboardButton("✅Выполнено", callback_data=f"complete:{number}")
        btn2 = types.InlineKeyboardButton("🗑️Удалить", callback_data=f"delete:{number}")
        btn3 = types.InlineKeyboardButton("🕐Перенести", callback_data=f"uncomplete:{number}")
        btn4 = types.InlineKeyboardButton("🔙Назад", callback_data=f"back_to_list")
        menu.add(btn1, btn3, btn2, btn4)
    return menu


def getHelpInfo(message):
    bot.send_message(message.chat.id, "❓ Как использовать бота?\n"
                     "▪ Используйте нижнее меню, чтобы создать напоминание, посмотреть и редактировать список ваших напоминаний\n"
                     "▪ Вводимые даты должны быть в будущем времени\n"
                    "▪ Вы можете удалить и переносить старые напоминания, но через время они удаляться автоматически")


@bot.message_handler(commands=["start"])
def startChat(message):
    with open('hello.jpg', 'rb') as photo_file:
        bot.send_photo(message.chat.id, photo_file)
    bot.send_message(message.chat.id, '👋 Привет, я твой бот-напоминалка RemindMe_bot,', reply_markup=get_main_menu())
    getHelpInfo(message)

@bot.message_handler(commands=["help"])
def help(message):
    getHelpInfo(message)



#---------------Добавление напоминания----------------#
@bot.message_handler(func=lambda message: message.text == '➕Создать напоминание')
def startRemind(message):
    msg = bot.send_message(message.chat.id, 'Введите текст напоминания', reply_markup=get_cancel_menu())
    bot.register_next_step_handler(msg, textStep)
def textStep(message):
    if message.text == "❌ Отмена":
       bot.send_message(message.chat.id, "✅ Создание напоминания отменено", reply_markup=get_main_menu())
       return
    tmp[message.chat.id] = {'text' : message.text}
    msg = bot.send_message(message.chat.id, "⏰ Теперь введите дату и время:\n"
            "Примеры:\n"
            "• 15 сентября 13:00\n"
            "• завтра 09:30\n"
            "• через 2 часа", reply_markup=get_cancel_menu())
    bot.register_next_step_handler(msg, dateStep)
def dateStep(message):
    try:
        if message.text == "❌ Отмена":
            bot.send_message(message.chat.id, "✅ Создание напоминания отменено", reply_markup=get_main_menu())
            return
        chat_id = message.chat.id
        date_str = message.text
        parsed_date = dateparser.parse(
            date_str,
            languages=["ru"],
            settings={
                'PREFER_DATES_FROM': 'future',
                'DATE_ORDER': 'DMY'
            }
        )

        if not parsed_date:
            raise ValueError("Не удалось распознать дату")
        if parsed_date < datetime.datetime.now():
            raise ValueError("Дата должна быть в будущем")

        text = tmp[chat_id]['text']

        if save_reminder(chat_id, text, parsed_date):
            bot.send_message(message.chat.id, "Напоминание установлено", reply_markup=get_main_menu())
        else:
            bot.send_message(message.chat.id, "Ошибка! Напоминание не сохранено", reply_markup=get_main_menu())
        del tmp[chat_id]

    except ValueError as error:
        msg = bot.send_message(
            message.chat.id,
            f"😵‍💫 Ошибка: {error}, пожалуйста, попробуте еще раз\n\n"
            "⏰ Введите дату и время:\n"
            "Примеры:\n"
            "• 15 сентября 13:00\n"
            "• завтра 09:30\n"
            "• через 2 часа",
                         reply_markup=get_cancel_menu())
        bot.register_next_step_handler(msg, dateStep)

def save_reminder(user_id, text, date):
    try:
        with open("reminds.json",  "r", encoding="utf-8") as saveFile:
            reminds = json.load(saveFile)


        chat_id_str = str(user_id)
        if chat_id_str not in reminds:
            reminds[str(user_id)] = []

        reminds[str(user_id)].append({
            "text" : text,
            "remind time" : date.isoformat(),
            "is completed" : False
        })

        with open("reminds.json", "w", encoding="utf-8") as saveFile:
            json.dump(reminds, saveFile, indent=4, ensure_ascii=False)

        return True
    except:
        return False





#---------------Редактирование напоминания----------------------#


def load_function(chat_id, message_id = None):
    with open("reminds.json", 'r', encoding='utf-8') as file:
        reminds = json.load(file)

    if str(chat_id) not in reminds:
        bot.send_message(chat_id, "🙃 У вас нет напоминаний", reply_markup=get_main_menu())
        return

    listed = (
        "(Прошедшие напоминания скоро будут удалены)\n"
        "Для редактирования напоминания выберите его номер\n\n\n"
        "📝 Вот ваши напоминания:\n\n")

    for i, rem in enumerate(reminds[str(chat_id)]):
        date = datetime.datetime.fromisoformat(rem["remind time"]).strftime("%d.%m.%Y %H:%M")
        if not rem["is completed"]:
            listed += f"{i + 1}. {rem['text']} ({date})\n"
        else:
            listed += f"▪️ {i + 1}. {rem['text']} (прошло)\n"

    if message_id:
        bot.edit_message_text(listed, chat_id=chat_id, message_id=message_id,
                              reply_markup=get_numbers(len(reminds[str(chat_id)])))
    else:
        bot.send_message(chat_id, listed, reply_markup=get_numbers(len(reminds[str(chat_id)])))

@bot.message_handler(func=lambda message: message.text == "📃Список")
def load_user_reminders(message):
    load_function(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_list")
def back_to_list(call):
    load_function(call.message.chat.id, call.message.message_id)
@bot.callback_query_handler(func=lambda call: call.data.startswith("num:"))
def handle(call):
    user_id = str(call.message.chat.id)
    number = int(call.data.split(":")[1]) - 1

    with open("reminds.json", "r", encoding="utf-8") as file:
        reminds = json.load(file)
    if user_id in reminds and 0 <= number < len(reminds[user_id]):
        date = datetime.datetime.fromisoformat(reminds[user_id][number]["remind time"]).strftime("%d.%m.%Y %H:%M")
        bot.send_message(call.message.chat.id,
                         f"Ваше напоминание:\n"
                         f"{reminds[user_id][number]['text']} ({date})",
                         reply_markup=get_edit_menu(number, reminds, str(call.message.chat.id)))
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(call.message.chat.id, "😵‍💫 Ошибка: Неправильный номер", reply_markup=get_main_menu())



@bot.callback_query_handler(func=lambda call: call.data.startswith("delete:"))
def delete(call):
    user_id = str(call.message.chat.id)
    number = int(call.data.split(":")[1])

    with open("reminds.json", "r+", encoding="utf-8") as file:
        reminds = json.load(file)
        if user_id in reminds and 0 <= number < len(reminds[user_id]):
            deleted = reminds[user_id].pop(number)
            if not reminds[user_id]:
                del reminds[user_id]

            file.seek(0)
            json.dump(reminds, file, indent=4, ensure_ascii=False)
            file.truncate()

            date = datetime.datetime.fromisoformat(deleted["remind time"]).strftime("%d.%m.%Y %H:%M")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id,
                             f"✅ Напоминание успешно удалено:\n{deleted['text']} ({date})", reply_markup=get_main_menu())
            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, "😵‍💫 Ошибка: Неверный номер")


@bot.callback_query_handler(func=lambda call: call.data.startswith("complete:"))
def complete(call):
    bot.answer_callback_query(call.id)
    user_id = str(call.message.chat.id)
    number = int(call.data.split(":")[1])
    with open("reminds.json", "r+", encoding="utf-8") as file:
        try:
            reminds = json.load(file)
            reminds[user_id][number]["is completed"] = True
            file.seek(0)
            json.dump(reminds, file, indent=4, ensure_ascii=False)
            file.truncate()
            bot.send_message(call.message.chat.id,
                             "✅ Напоминание успешно отмечено как выполненное", reply_markup=get_main_menu())
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            bot.send_message(call.message.chat.id, "😵‍💫 Простите, возникла непредвиденная ошибка. Пожалуйста попробуйте еще раз.", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith("uncomplete:"))
def uncomplete(call):
    bot.answer_callback_query(call.id)
    user_id = str(call.message.chat.id)
    number = int(call.data.split(":")[1])

    try:
        msg = bot.send_message(call.message.chat.id, "Теперь введите новые дату и время:\n"
                                                    "Примеры:\n"
                                                    "• 15 сентября 13:00\n"
                                                    "• завтра 09:30\n"
                                                    "• через 2 часа", reply_markup=get_cancel_menu())

        bot.register_next_step_handler(msg, lambda message: uncompleteDateEnter(message, user_id, number, call))
    except:
        bot.send_message(call.message.chat.id, "😵‍💫 Простите, возникла непредвиденная ошибка. Пожалуйста попробуйте еще раз.", reply_markup=get_main_menu())

def uncompleteDateEnter(message, user_id, number, call):
    try:
        if message.text == "❌ Отмена":
            bot.send_message(message.chat.id, "✅ Перенос напоминания отменен", reply_markup=get_main_menu())
            return
        date_str = message.text
        parsed_date = dateparser.parse(
            date_str,
            languages=["ru"],
            settings={
                'PREFER_DATES_FROM': 'future',
                'DATE_ORDER': 'DMY'
            }
        )

        if not parsed_date:
            raise ValueError("Не удалось распознать дату")
        if parsed_date < datetime.datetime.now():
            raise ValueError("Дата должна быть в будущем")

        with open("reminds.json", "r+", encoding="utf-8") as file:
            reminds = json.load(file)
            reminds[user_id][number]["remind time"] = parsed_date.isoformat()
            reminds[user_id][number]["is completed"] = False

            file.seek(0)
            json.dump(reminds, file, indent=4, ensure_ascii=False)
            file.truncate()

            bot.send_message(message.chat.id,"✅ Напоминание успешно перенесено", reply_markup=get_main_menu())
            bot.delete_message(message.chat.id, message.message_id)

    except ValueError as error:
        msg = bot.send_message(
            message.chat.id,
            f"😵‍💫 Ошибка: {error}. Пожалуйста, попробуйте еще раз\n\n"
            "⏰ Введите дату и время:\n"
            "Примеры:\n"
            "• 15 сентября 13:00\n"
            "• завтра 09:30\n"
            "• через 2 часа",
            reply_markup=get_cancel_menu())
        bot.register_next_step_handler(msg, lambda message: uncompleteDateEnter(message, user_id, number, call))


bot.infinity_polling()
