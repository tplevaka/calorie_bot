import asyncio
import io
import os
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from google import genai
from google.genai import types as genai_types
from PIL import Image, ImageDraw, ImageFont

# Считываем секреты из переменных окружения сервера
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def create_infographic(image_bytes: bytes, text_data: str) -> io.BytesIO:
  image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

  kcal_match = re.search(r"Калорийность:\s*\*?~?\s*(\d+[-—]?\d*)", text_data, re.IGNORECASE)
  protein_match = re.search(r"Белки:\s*\*?~?\s*(\d+)", text_data, re.IGNORECASE)
  fat_match = re.search(r"Жиры:\s*\*?~?\s*(\d+)", text_data, re.IGNORECASE)
  carb_match = re.search(r"Углеводы:\s*\*?~?\s*(\d+)", text_data, re.IGNORECASE)

  kcal = kcal_match.group(1) if kcal_match else "450"
  protein = protein_match.group(1) if protein_match else "30"
  fat = fat_match.group(1) if fat_match else "15"
  carb = carb_match.group(1) if carb_match else "40"

  base_width = 800
  w_percent = base_width / float(image.size[0])
  h_size = int(float(image.size[1]) * float(w_percent))
  image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)

  draw = ImageDraw.Draw(image)

  try:
    font_large = ImageFont.truetype("arial.ttf", 36)
    font_main = ImageFont.truetype("arial.ttf", 22)
  except IOError:
    font_large = ImageFont.load_default()
    font_main = ImageFont.load_default()

  card_w, card_h = 280, 220
  padding = 20
  x1 = base_width - card_w - padding
  y1 = padding
  x2 = base_width - padding
  y2 = y1 + card_h

  draw.rounded_rectangle([x1, y1, x2, y2], radius=20, fill=(255, 255, 255))
  draw.text((x1 + 20, y1 + 15), f"{kcal} ккал", fill=(0, 0, 0), font=font_large)

  draw.ellipse([x1 + 20, y1 + 75, x1 + 35, y1 + 90], fill=(46, 204, 113))
  draw.text((x1 + 45, y1 + 72), f"Белки: {protein} г", fill=(50, 50, 50), font=font_main)

  draw.ellipse([x1 + 20, y1 + 115, x1 + 35, y1 + 130], fill=(241, 196, 15))
  draw.text((x1 + 45, y1 + 112), f"Жиры: {fat} г", fill=(50, 50, 50), font=font_main)

  draw.ellipse([x1 + 20, y1 + 155, x1 + 35, y1 + 170], fill=(52, 152, 219))
  draw.text((x1 + 45, y1 + 152), f"Углеводы: {carb} г", fill=(50, 50, 50), font=font_main)

  output_stream = io.BytesIO()
  image.save(output_stream, format="JPEG", quality=95)
  output_stream.seek(0)
  return output_stream


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
  await message.answer(
      "Привет! Отправь мне фото еды, и я сформирую инфографику с КБЖУ прямо на фото."
  )


@dp.message(F.photo)
async def handle_photo(message: types.Message):
  await message.answer("Создаю карточку КБЖУ, подождите немного...")

  photo = message.photo[-1]
  file = await bot.get_file(photo.file_id)
  file_bytes = await bot.download_file(file.file_path)
  image_data = file_bytes.read()

  try:
    prompt = (
        "Определи блюдо на фото и посчитай КБЖУ.\n"
        "Ответь СТРОГО в следующем формате:\n"
        "Блюдо: [Название]\n"
        "Калорийность: [число] ккал\n"
        "Белки: [число] г\n"
        "Жиры: [число] г\n"
        "Углеводы: [число] г"
    )

    response = gemini_client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            genai_types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
            prompt,
        ],
    )

    raw_text = response.text
    infographic_bytes = create_infographic(image_data, raw_text)

    photo_file = types.BufferedInputFile(infographic_bytes.read(), filename="result.jpg")
    await message.answer_photo(photo=photo_file, caption=f"📊 **Результат:**\n\n{raw_text}")

  except Exception as e:
    await message.answer(f"Произошла ошибка при обработке: {e}")


async def main():
  print("Бот запущен с генерацией инфографики!")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())