"""Build a PDF containing classified questions matching one unit."""
import base64
import io
import json
from PIL import Image, ImageDraw, ImageFont
import classifications


def matching_questions(con, unit):
    if type(unit) is not int or unit not in classifications.UNITS:
        raise ValueError('Enter a unit number from 1 to 8.')
    questions = []
    for encoded, numbers in con.execute('SELECT question_json,unit_numbers FROM question_classifications ORDER BY question_id'):
        if unit in json.loads(numbers):
            questions.append(json.loads(encoded))
    return sorted(questions, key=lambda q: (q.get('filename',''), q.get('order',q.get('question_number',0)), q['id']))


def build_pdf(con, unit):
    questions = matching_questions(con, unit)
    if not questions:
        raise ValueError(f'No classified questions match Unit {unit}. Classify questions first or choose another unit.')
    # Letter size at 144 DPI. Render only the stored per-question crops.
    width, height, margin = 1224, 1584, 64
    heading_font = ImageFont.load_default(size=25)
    small_font = ImageFont.load_default(size=18)
    pages = []
    try:
        for index, question in enumerate(questions, 1):
            images = question.get('images', [])
            if not images:
                raise ValueError(f'Question {question.get("question_number")} has no saved image. Regenerate questions.json and reclassify it.')
            for part, image_data in enumerate(images, 1):
                try:
                    raw = base64.b64decode(image_data['base64'], validate=True)
                    with Image.open(io.BytesIO(raw)) as original:
                        image = original.convert('RGB')
                except Exception as exc:
                    raise ValueError(f'Unable to read image for Question {question.get("question_number")}.') from exc
                page = Image.new('RGB', (width,height), 'white')
                draw = ImageDraw.Draw(page)
                draw.text((margin,35), f'Unit {unit}: {classifications.UNITS[unit]}', font=heading_font, fill='#21372f')
                source = f'{index}/{len(questions)} | {question.get("filename", "")} | Question {question.get("question_number", "")}'
                while draw.textbbox((0,0),source,font=small_font)[2] > width-2*margin:
                    source=source[:-4]+'…'
                draw.text((margin,75),source,font=small_font,fill='#526453')
                draw.text((margin,105),'Assigned units: '+', '.join(map(str,question['unit_numbers'])),font=small_font,fill='#526453')
                image.thumbnail((width-2*margin,height-210),Image.Resampling.LANCZOS)
                page.paste(image,((width-image.width)//2,150))
                image.close()
                draw.text((margin,height-40),f'Page {len(pages)+1} | Question part {part}/{len(images)}',font=small_font,fill='#526453')
                pages.append(page)
        output = io.BytesIO()
        pages[0].save(output,format='PDF',save_all=True,append_images=pages[1:],resolution=144.0,
                      title=f'Unit {unit} - {classifications.UNITS[unit]}',author='Question Library')
        return output.getvalue(), len(questions)
    finally:
        for page in pages:
            page.close()
