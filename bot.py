import datetime
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.dispatcher.filters import Text
from aiogram.utils import executor, exceptions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.utils.exceptions import BotBlocked
from low_level.auth import *
from low_level.parser import *
from resources.models import *
from resources.states import *

term_begin = 1

''' TODO:
    Номер недели с которой начался семестр - 2, началось со знаменателя. Т.е. если деление текущей недели на 2 дает остаток, значит это числитель, иначе знаменатель.
    В базе данных False - это числитель, True - знаменатель.
    Нужно создать переменную, которая хранит с чего начался семестр - с числителя или знаменателя, для учета этих данных при вычислени.
    Счет дней в базе начинаем с 0 (понедельник), и до 6 (воскресенье)
    1) Написать функцию для расчета числителя/знаменателя.
    2) Написать команду для вытаскивания из базы расписания для конкретной группы с учетом замен.
'''

def week_denominator_calculate(weeknum: int):
    if term_begin == 0:
        if weeknum % 2 != 0:
            return 1
        else:
            return 0
    elif term_begin == 1:
        if weeknum % 2 != 0:
            return 0
        else:
            return 1

def both_week_calculate(current_denominator):
    if current_denominator == 0:
        return (0,1)
    elif current_denominator == 1:
        return (0,)            

async def eduhouse_check():
    files = download_docs()
    db_files = session.query(ParsedFiles).all()
    for filecheck in db_files:
        if filecheck.filename not in files:
            session.delete(filecheck)
    for file in files:
        if not session.query(ParsedFiles).filter(ParsedFiles.filename == file).first():
            new_file = ParsedFiles(filename=file)
            session.add(new_file)
            substitutions = parse(file)
            for sub in substitutions:
                group = session.query(Group).filter(Group.group_name == sub.group).first()
                if not group:
                    group = Group(group_name=sub.group)
                    session.add(group)
                sub_db = Substitution(file=new_file, pair_num=sub.pair_num, init_pair=sub.init_pair,
                                      sub_pair=sub.sub_pair, cab=sub.cab, group=group)
                session.add(sub_db)
                session.commit()
            remove_cache()
        else:
            os.remove(file)
            continue
    session.commit()


async def notification(user: Auth):
    if not user.notification:
        return
    if len(user.group.subs) == 0:
        try:
            await bot.send_message(user.user_id, "Привет! Для твоей группы не найдено актуальных замен")
        except BotBlocked:
            return
    else:
        await bot.send_message(user.user_id,
                               "Привет! Начинаем рассылку актуальных замен\n"
                               "Для твоей группы найдены следующие замены: ")
    for substitution in user.group.subs:
        try:
            date = substitution.file.filename[0:10]
            formated_date = date.replace(".", "/")
            filter_date = datetime.datetime.strptime(formated_date, '%d/%m/%Y').date()
            current_date = datetime.datetime.today().date()
            if filter_date < current_date:
                continue
            elif filter_date >= current_date:
                await bot.send_message(user.user_id,
                                       f"📌 Замещение на {date}:\n🔢 Номер пары: {substitution.pair_num}\n"
                                       f"📖 Предмет по расписанию: {substitution.init_pair}\n📝 "
                                       f"Замена: {substitution.sub_pair}\n🚪 "
                                       f"Кабинет: {substitution.cab}")
        except BotBlocked:
            return


bot = Bot(token=os.environ["BOT_TOKEN"], parse_mode='html')
storage = RedisStorage2("localhost", 6379, pool_size=40, prefix="interesting_fsm_key")
dp = Dispatcher(bot, storage=storage)
scheduler = AsyncIOScheduler()


@dp.message_handler(commands=["start", "begin"], state="*")
async def start(message: types.Message):
    auth = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    if auth:
        await UserState.user_authorized.set()
        await message.answer(
            f"Привет! 👋\nТы ранее уже авторизовывался в группе {auth.group.group_name}\n"
            f"Если ты хочешь сменить группу, используй команду /change_group\n"
            f"Для получения справки и списка доступных команд используй команду /help\n"
            f"(Разработал и выпустил - Каравайчик Александр)")
    else:
        await UserState.user_default_state.set()
        await message.answer(
            text="Привет! 👋\nПрежде чем начать пользоваться ботом, тебе необходимо авторизоваться.\n"
                 "Для этого используй команду <i>/auth</i>\n"
                 "(Разработал и выпустил - Каравайчик Александр)")


@dp.message_handler(commands=["auth"], state=UserState.user_default_state)
async def ask_group(message: types.Message):
    await UserState.user_group_required.set()
    await message.answer(
        "✏️ Для того, чтобы тебя авторизовать, мне необходимо знать, в какой группе ты учишься. "
        "Напиши свою учебную группу, например 9ПО-21. "
        "Если твоей группы нет в списке, значит для нее еще не было добавлено замещений. "
        "Не переживай, как только они появятся, твоя группа будет добавлена в базу.")


@dp.message_handler(state=UserState.user_group_required)
async def authorization(message: types.Message):
    try_group = session.query(Group).filter(Group.group_name == message.text).first()
    if try_group is None:
        await message.answer(
            "⛔️ Ошибка: такой группы не найдено! "
            "Проверь правильность написания, если все правильно, значит твоей группы "
            "еще нет в базе")
        return
    new_auth = Auth(user_id=message.from_user.id, group_id=try_group.id)
    session.add(new_auth)
    session.commit()
    scheduler.add_job(notification, "cron", hour=new_auth.hour, minute=new_auth.minute,
                      id=new_auth.user_id, args=(new_auth,))
    await message.answer(f"✅ Вы успешно авторизовались в группе {try_group.group_name}")
    await UserState.user_authorized.set()


@dp.message_handler(commands=["change_group"], state=UserState.user_authorized)
async def ask_group_change(message: types.Message):
    await UserState.user_changing_group.set()
    await message.answer("✏️ Напиши новую группу, в которой ты хочешь авторизоваться")


@dp.message_handler(state=UserState.user_changing_group)
async def group_change(message: types.Message):
    try_group = session.query(Group).filter(Group.group_name == message.text).first()
    if try_group is None:
        await message.answer(
            "⛔️ Ошибка: такой группы не найдено! Проверь правильность написания, "
            "если все правильно, значит твоей группы еще нет в базе")
        return
    user_to_change = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    user_to_change.group = try_group
    session.add(user_to_change)
    session.commit()
    await message.answer(f"✅ Вы успешно авторизовались в группе {try_group.group_name}")
    await UserState.user_authorized.set()


@dp.message_handler(commands=["substitutions"], state=UserState.user_authorized)
async def get_substitutions(message: types.Message):
    auth = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    substitutions = session.query(Substitution).filter(Substitution.group == auth.group).all()
    if not substitutions:
        await message.answer("⭕️ Замещений для твоей группы не обнаружено")
    else:
        for substitution in substitutions:
            date = substitution.file.filename[0:10]
            formated_date = date.replace(".", "/")
            filter_date = datetime.datetime.strptime(formated_date, '%d/%m/%Y').date()
            current_date = datetime.datetime.today().date()
            if filter_date < current_date:
                continue
            elif filter_date >= current_date:
                await message.answer(
                    f"📌 Замещение на {date}:\n"
                    f"🔢 Номер пары: {substitution.pair_num}\n"
                    f"📖 Предмет по расписанию: {substitution.init_pair}\n"
                    f"📝 Замена: {substitution.sub_pair}\n"
                    f"🚪 Кабинет: {substitution.cab}")


@dp.message_handler(commands=["disable_notifications"], state=UserState.user_authorized)
@dp.message_handler(content_types=["text"], text="Отключить рассылку", state=UserState.user_authorized)
async def disable_notifications(message: types.Message):
    auth = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    if not auth.notification:
        await message.answer("⛔️ Ошибка: уведомления уже отключены", reply_markup=types.ReplyKeyboardRemove())
        return
    auth.notification = False
    session.add(auth)
    session.commit()
    await message.answer("✅ Уведомления о заменах успешно отключены", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands=["enable_notifications"], state=UserState.user_authorized)
@dp.message_handler(content_types=["text"], text="Включить рассылку", state=UserState.user_authorized)
async def enable_notifications(message: types.Message):
    auth = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    if auth.notification:
        await message.answer("⛔️ Ошибка: уведомления уже включены", reply_markup=types.ReplyKeyboardRemove())
        return
    auth.notification = True
    session.add(auth)
    session.commit()
    await message.answer("✅ Уведомления о заменах успешно включены", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands=["help"], state=[UserState.user_default_state, UserState.user_authorized])
async def help(message: types.Message):
    await message.answer(
        "📜 Справка: Данный бот помогает студентам узнавать об изменениях в раписании, которые выкладываются на портале"
        "\nРазработал студент группы 9ПО-21 Каравайчик Александр\n"
        "Список команд:\n"
        "<i>/start</i> - Начало работы\n"
        "<i>/help</i> - Справка\n"
        "<i>/auth</i> - Авторизация\n"
        "<i>/change_group</i> - Смена группы\n"
        "<i>/substitutions</i> - Получение актуальных замен для твоей группы\n"
        "<i>/disable_notifications</i> - Отключение ежедневной рассылки\n"
        "<i>/enable_notifications</i> - Включение ежедневной рассылки")


@dp.errors_handler(exception=exceptions.RetryAfter)
async def retry_after_handler(update: types.Update, exception: exceptions.RetryAfter):
    if update.message is not None:
        await bot.send_message(update.message.from_user.id,
                               f"Произошла ошибка на сервере! Пожалуйста, подождите {exception.timeout}")

    return True


@dp.message_handler(commands=["config_time"], state=UserState.user_authorized)
@dp.message_handler(content_types=["text"], text="Настройка времени рассылки", state=UserState.user_authorized)
async def config_time(message: types.Message, state: FSMContext):
    cancel = types.ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True).add(types.KeyboardButton(text="Отмена"))
    await message.answer("Для настройки персонального времени рассылки пришли мне час (от 0 до 23)",
                         reply_markup=cancel)
    await UserState.user_setting_hour.set()


@dp.message_handler(content_types=["text"], text="Отмена",
                    state=[UserState.user_setting_hour, UserState.user_setting_minute])
async def cancellation(message: types.Message):
    await UserState.user_authorized.set()
    await message.answer("Действие отменено", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=UserState.user_setting_hour)
async def hour_input(message: types.Message, state: FSMContext):
    try:
        hour = int(message.text)
    except ValueError:
        await message.answer("⛔️ Ошибка! Введен неверный формат времени")
        return
    else:
        if hour < 0 or hour > 23:
            await message.answer("⛔️ Ошибка! Введен неверный формат времени")
            return
        await UserState.user_setting_minute.set()
        await state.update_data(hour=hour)
        await message.answer("Хорошо, для завершения настройки пришли мне минуту (от 0 до 59)")


@dp.message_handler(state=UserState.user_setting_minute)
async def time_set(message: types.Message, state: FSMContext):
    try:
        minute = int(message.text)
    except ValueError:
        await message.answer("⛔️ Ошибка! Введен неверный формат времени")
    else:
        if minute < 0 or minute > 59:
            await message.answer("⛔️ Ошибка! Введен неверный формат времени")
            return
        fsm_data = await state.get_data()
        hour = fsm_data.get("hour")
        auth = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
        auth.hour = hour
        auth.minute = minute
        auth.notification = True
        scheduler.remove_job(auth.user_id)
        scheduler.add_job(notification, "cron", hour=hour, minute=minute, id=auth.user_id, args=(auth,))
        session.add(auth)
        session.commit()
        await UserState.user_authorized.set()
        await message.answer(f"✅ Готово! Теперь ты будешь получать рассылку о заменах в {hour}:{minute:02}",
                             reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands=["settings"], state=UserState.user_authorized)
async def settings(message: types.Message):
    settings_menu = types.ReplyKeyboardMarkup(row_width=1, one_time_keyboard=True)
    auth_data = session.query(Auth).filter(Auth.user_id == message.from_user.id).first()
    if auth_data.notification is False:
        enable_notifications_button = types.KeyboardButton(text="Включить рассылку")
        settings_menu.add(enable_notifications_button)
    else:
        disable_notifications_button = types.KeyboardButton(text="Отключить рассылку")
        settings_menu.add(disable_notifications_button)

    notification_config_button = types.KeyboardButton(text="Настройка времени рассылки")
    settings_menu.add(notification_config_button)

    await message.answer("Список настроек: \n", reply_markup=settings_menu)

@dp.message_handler(commands=["timetable_today"], state=UserState.user_authorized)
async def timetable_today(message: types.Message):
    now = datetime.datetime.now()
    current_denominator = week_denominator_calculate(now.isocalendar().week)
    auth = session.query(Auth).filter(Auth.user_id==message.from_user.id).first()
    timetable = session.query(Timetable).filter(Timetable.group_id==auth.group_id, Timetable.denominator==current_denominator, Timetable.week_day_num==now.weekday()).all()
    if timetable is None:
        await message.answer("Ошибка: не найдено данных для твоего расписания! Возможно, твоя группа еще не появилась в базе данных в таблице расписаний")
        return
    subs = session.query(Substitution).filter(Substitution.group==auth.group).all()
    current_date = f"{now.day}.{now.month:02}.{now.year}"
    result_text = f"📅 Твое расписание на {current_date}\n"
    for filter_lesson in timetable:
        if current_denominator == 0 and filter_lesson.both_weeks in (0,1):
            continue
        elif current_denominator == 1 and filter_lesson == 1:
            continue
        else:
            timetable.remove(filter_lesson)

    for lesson in timetable:
        if len(subs) == 0:
            if lesson.pair_name == "-":
                continue
            else:
                result_text += f"🕒 {lesson.pair_num} пара:\n📖 Предмет по расписанию: {lesson.pair_name}\n🚪 Кабинет: {lesson.cab}\n\n"
        else:
            for substitution in subs:
                if substitution.pair_num == lesson.pair_num and substitution.file.filename[0:10] == current_date:
                    result_text += f"🕒 {substitution.pair_num} пара:\n📖 Предмет по замещению: {substitution.sub_pair}\n🚪 Кабинет: {substitution.cab}\n\n"
                else:
                    if lesson.pair_name == "-":
                        continue
                    else:
                        result_text += f"🕒 {lesson.pair_num} пара:\n📖 Предмет по расписанию: {lesson.pair_name}\n🚪 Кабинет: {lesson.cab}\n\n"
    await message.answer(result_text)

@dp.message_handler(commands=["timetable_tomorrow"], state=UserState.user_authorized)
async def timetable_today(message: types.Message):
    tomorrow = datetime.datetime.today() + datetime.timedelta(days=1)
    current_denominator = week_denominator_calculate(tomorrow.isocalendar().week)
    auth = session.query(Auth).filter(Auth.user_id==message.from_user.id).first()
    timetable = session.query(Timetable).filter(Timetable.group_id==auth.group_id, Timetable.denominator==current_denominator, Timetable.week_day_num==tomorrow.weekday()).all()
    print(current_denominator)
    print(timetable)
    if timetable is None:
        await message.answer("Ошибка: не найдено данных для твоего расписания! Возможно, твоя группа еще не появилась в базе данных в таблице расписаний")
        return
    subs = session.query(Substitution).filter(Substitution.group==auth.group).all()
    tomorrow_date = f"{tomorrow.day}.{tomorrow.month:02}.{tomorrow.year}"
    result_text = f"📅 Твое расписание на {tomorrow_date}\n"
    for filter_lesson in timetable:
        if current_denominator == 0 and filter_lesson.both_weeks in (0,1):
            continue
        elif current_denominator == 1 and filter_lesson == 1:
            continue
        else:
            timetable.remove(filter_lesson)

    for lesson in timetable:
        if len(subs) == 0:
            if lesson.pair_name == "-":
                continue
            else:
                result_text += f"🕒 {lesson.pair_num} пара:\n📖 Предмет по расписанию: {lesson.pair_name}\n🚪 Кабинет: {lesson.cab}\n\n"
        else:
            for substitution in subs:
                if substitution.pair_num == lesson.pair_num and substitution.file.filename[0:10] == tomorrow_date:
                    result_text += f"🕒 {substitution.pair_num} пара:\n📖 Предмет по замещению: {substitution.sub_pair}\n🚪 Кабинет: {substitution.cab}\n\n"
                else:
                    if lesson.pair_name == "-":
                        continue
                    else:
                        result_text += f"🕒 {lesson.pair_num} пара:\n📖 Предмет по расписанию: {lesson.pair_name}\n🚪 Кабинет: {lesson.cab}\n\n"
    await message.answer(result_text)

if __name__ == "__main__":
    scheduler.add_job(eduhouse_check, "interval", hours=1)
    users = session.query(Auth).all()
    for user in users:
        scheduler.add_job(notification, "cron", hour=user.hour, minute=user.minute, id=user.user_id, args=(user,))
    scheduler.start()
    executor.start_polling(dp, skip_updates=True)
