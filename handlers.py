from aiogram import Router 
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command 
from aiogram.fsm.context import FSMContext 
import aiohttp
import aiofiles
import os
import json
from states import ProfileInfo, CaloriesCount
import requests
import re

router = Router()

def extract_numbers(text):
    pattern = r'\d+'
    numbers = re.findall(pattern, text)
    return numbers

def get_food_info(product_name):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:  # Проверяем, есть ли найденные продукты
            first_product = products[0]
            return {
                'name': first_product.get('product_name', 'Неизвестно'),
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
        return None
    print(f"Ошибка: {response.status_code}")
    return None

def check_water_norm(d: dict, temperature : int = 20):
    return d['weight'] * 30 + d['mins_active'] // 30 * 500 + 500 - 1000 * (temperature > 25)

def check_calories_norm(d: dict, mins_active: float):
    return 10 * d['weight'] + 6.25 * d['height'] - 5 * d['age'] + mins_active * 10

async def load_user_data():
    if os.path.exists('user_data.json'):
        async with aiofiles.open('user_data.json', 'r', encoding='utf-8') as f:
            contents = await f.read()
            return json.loads(contents)
    return {}

async def save_user_data(data):
    async with aiofiles.open('user_data.json', 'w', encoding='utf-8') as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

@router.message(Command('start'))
async def cmd_start(message: Message):
    await message.reply('Привет! Я твой бот по контролю еды, воды и тренировок')

@router.message(Command('help'))
async def cmd_help(message: Message):
    await message.reply(
        '''
        Доступные команды:
        /start - начало работы
        /set_profile - заполнение информации о пользователе
        /log_water - записывает количество потребленной воды в милилитрах
        /log_food - записывает количество потребленных калорий
        /check_progress - показывает прогресс по калориям и воде 
        '''
    )

# заполняем профиль пользователя
@router.message(Command('set_profile'))
async def start_set_profile(message: Message, state: FSMContext):
    user_name = message.from_user.username
    to_json = json.dumps({user_name : {}})
    await save_user_data(to_json)
    await message.reply('Какой у вас вес?')
    await state.set_state(ProfileInfo.weight)

@router.message(ProfileInfo.weight)
async def process_weight(message: Message, state: FSMContext):
    try: 
        await state.update_data(weight=float(message.text)) 
    except:
        await message.answer('Укажите вес в формате числа, пожалуйста')
        return
    await message.answer('Сколько у вас минут активности в день?')
    await state.set_state(ProfileInfo.mins_active)

@router.message(ProfileInfo.mins_active)
async def process_mins_active(message: Message, state: FSMContext):
    try: 
        await state.update_data(mins_active=float(message.text)) 
    except:
        await message.answer('Укажите активность в формате числа, пожалуйста')
        return
    await message.answer('В каком городе вы находитесь?')
    await state.set_state(ProfileInfo.city)

@router.message(ProfileInfo.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text) 
    await message.answer('Какой у вас рост?')
    await state.set_state(ProfileInfo.height)

@router.message(ProfileInfo.height)
async def process_city(message: Message, state: FSMContext):
    try:
        await state.update_data(height=float(message.text)) 
    except:
        await message.answer('Укажите рост в формате числа, пожалуйста')
        return
    await message.answer('Сколько вам полных лет?')
    await state.set_state(ProfileInfo.age)

@router.message(ProfileInfo.age)
async def process_age(message: Message, state: FSMContext):
    try:
        await state.update_data(age=int(message.text)) 
    except:
        await message.answer('Укажите возраст в формате числа, пожалуйста')
        return
    user_name = message.from_user.username
    data = await state.get_data()
    weight = data.get('weight')
    mins_active = data.get('mins_active')
    city = data.get('city')
    age = data.get('age')
    height = data.get('height')
    user_data = await load_user_data()
    user_data = json.loads(user_data)
    user_data[user_name]['weight'] = weight
    user_data[user_name]['mins_active'] = mins_active
    user_data[user_name]['city'] = city
    user_data[user_name]['age'] = age
    user_data[user_name]['height'] = height
    await save_user_data(user_data)
    await message.reply('Ваши данные сохранены!')
    await state.clear()

# потребление воды
@router.message(Command('log_water'))
async def log_water(message: Message):
    user_name = message.from_user.username
    try:
        water = float(message.text.split(' ')[1].strip())
        user_data = await load_user_data()
        
        if 'water' not in user_data[user_name].keys():
            user_data[user_name]['water'] = water
            
        else:
            user_data[user_name]['water'] += water
        await save_user_data(user_data)
        water_norm = check_water_norm(user_data[user_name])
        water_gap = water_norm - user_data[user_name]['water']
        if water_gap > 0:
            await message.answer(f'Записал {water} мл. Вам осталось еще {water_gap} мл до нормы')
        else:
            await message.answer(f'Записал {water} мл. Ваша норма воды выполнена!')
    except:
        await message.answer('Неправильно указан формат данных. Укажите количество выпитых милилитров в формате числа через пробел после команды')
    
    
@router.message(Command('log_food'))
async def log_food(message: Message, state: FSMContext):
    await message.answer('Смотрю каллорийность продукта...')
    user_name = message.from_user.username
    try:
        food = message.text.split(' ')[1].strip()
        food_js = get_food_info(food)
        calories = food_js['calories']
        await state.update_data(calories=float(calories))
        await state.set_state(CaloriesCount.calories)
        await message.answer(f'Каллорийность {food} - {calories} на 100 грамм. Сколько грамм вы съели?')
    except:
        await message.answer('Неправильно указан формат данных. Укажите продукт в формате строки через пробел после команды')

@router.message(CaloriesCount.calories)
async def compute_calories(message: Message, state: FSMContext):
    user_name = message.from_user.username
    try:
        gramms_eaten = float(message.text.strip())
        await message.answer(f'{gramms_eaten}')
        data = await state.get_data()
        calories = data.get('calories')
        total_calories = gramms_eaten / 100 * calories
        user_data = await load_user_data()
        if 'total_calories' not in user_data[user_name].keys():
            user_data[user_name]['total_calories'] = total_calories
        else:
            user_data[user_name]['total_calories'] += total_calories
        await save_user_data(user_data)
        norm_calories = check_calories_norm(user_data[user_name], user_data[user_name]['mins_active'])
        calories_gap = norm_calories - user_data[user_name]['total_calories']
        if calories_gap > 0:
            await message.answer(f'Записал {round(total_calories, 2)} калорий. Текущее количество потребленных калорий: {round(user_data[user_name]['total_calories'], 2)}. Осталось до дневной нормы {calories_gap}')
        else:
            await message.answer(f'Записал {round(total_calories, 2)} калорий. Текущее количество потребленных калорий: {round(user_data[user_name]['total_calories'], 2)}. Вы потребили калорий больше чем дневная норма на  {-1 * calories_gap}')
        await state.clear()       
    except:
        await message.answer('Данные набраны в неправильном формате, пожалуйста используйте числа для указания количества съеденного продукта')

@router.message(Command('log_workout'))
async def log_workout(message: Message):
    user_name = message.from_user.username
    try:   
        mins_active = float(extract_numbers(message.text)[0])
        await message.answer(f'{mins_active}')
        user_data = await load_user_data()
        if 'mins_active' not in user_data[user_name].keys():
            user_data[user_name]['mins_active'] = mins_active
        else:
            user_data[user_name]['mins_active'] += mins_active
        await save_user_data(user_data)
        await message.answer(f'Записал {round(mins_active, 2)} минут активности. Текущее количество минут активности: {round(user_data[user_name]['mins_active'], 2)}')
    except:
        await message.answer('Вы не указали сколько минут вы занимались спортом. Укажите, пожалуйста, время в минутах')

@router.message(Command('check_progress'))
async def check_progress(message: Message):
    user_name = message.from_user.username
    user_data = await load_user_data()
    try:
        calories = user_data[user_name]['total_calories']
        norm_calories = check_calories_norm(user_data[user_name], user_data[user_name]['mins_active'])
        calories_gap = norm_calories - calories
        if calories_gap < 0:
            calories_paste = f'Вы превысили калораж на {-1 * calories_gap}'
        else:
            calories_paste = f'Осталось: {calories_gap} калорий'
        try: 
            water = user_data[user_name]['water']
            norm_water = check_water_norm(user_data[user_name])
            water_gap = norm_water - water
            if water_gap < 0:
                water_paste = f'Вы выполнили дневную норму!'
            else:
                water_paste = f'Осталось: {water_gap} мл'

            await message.answer(f'Прогресс:\nКалории:\nПотреблено: {calories} калории\n{calories_paste}\n\n'
                                f'Вода:\nВыпито: {water} мл\n{water_paste}')
        except:
            await message.answer('Вы не заполняли воду')
        
    except:
        await message.answer('Вы не заполняли калории')
    