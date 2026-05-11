"""
Контракт-61: Сервис генерации PDF-документов.
Генерирует анкеты и рапорты на основе данных кандидата.
"""
import io
import logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFService:
    def __init__(self):
        # Попытка найти кириллический шрифт в системе или в проекте
        self.font_name = "Helvetica"
        try:
            # Если есть шрифт в проекте, можно подключить:
            # pdfmetrics.registerFont(TTFont('DejaVu', 'assets/fonts/DejaVuSans.ttf'))
            # self.font_name = "DejaVu"
            pass
        except Exception as e:
            logger.warning("⚠️ Не удалось загрузить кириллический шрифт: %s", e)

    def generate_candidate_card(self, candidate) -> bytes:
        """Сформировать анкету кандидата в PDF."""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Заголовок
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 20*mm, "АНКЕТА КАНДИДАТА #{}".format(candidate.id))
        
        c.setFont("Helvetica", 12)
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.line(20*mm, height - 25*mm, width - 20*mm, height - 25*mm)

        y = height - 40*mm
        
        def draw_field(label, value):
            nonlocal y
            c.setFont("Helvetica-Bold", 10)
            c.drawString(20*mm, y, "{}:".format(label))
            c.setFont("Helvetica", 10)
            c.drawString(60*mm, y, str(value) if value else "—")
            y -= 7*mm

        draw_field("ФИО", candidate.full_name)
        draw_field("Телефон", candidate.phone)
        draw_field("Источник", candidate.source)
        draw_field("Дата создания", candidate.created_at.strftime("%d.%m.%Y %H:%M"))
        
        y -= 5*mm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20*mm, y, "СТАТУСЫ:")
        y -= 8*mm
        
        draw_field("Билет", candidate.ticket_status.value)
        if candidate.arrival_date:
            draw_field("Прибытие", candidate.arrival_date.strftime("%d.%m.%Y"))
        draw_field("Медицина", candidate.medical_status.value)
        draw_field("Обучение", candidate.registration_status.value)

        if candidate.notes:
            y -= 5*mm
            c.setFont("Helvetica-Bold", 10)
            c.drawString(20*mm, y, "ЗАМЕТКИ:")
            y -= 6*mm
            c.setFont("Helvetica", 9)
            text_obj = c.beginText(20*mm, y)
            text_obj.textLines(candidate.notes)
            c.drawText(text_obj)

        # Футер
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(20*mm, 15*mm, "Сгенерировано системой Контракт-61: {}".format(datetime.now().strftime("%d.%m.%Y %H:%M")))
        
        c.showPage()
        c.save()
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

pdf_service = PDFService()
