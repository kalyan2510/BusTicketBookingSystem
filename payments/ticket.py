"""QR code and PDF e-ticket generation."""
import io
import os
from decimal import Decimal

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

NAVY = HexColor("#0B1F3A")
NAVY_SOFT = HexColor("#14305A")
RED = HexColor("#E63946")
GOLD = HexColor("#F4B400")
LIGHT = HexColor("#F4F7FC")
GREY = HexColor("#6B7A90")
GREEN = HexColor("#1F9D6B")


def _verify_url(booking, request=None):
    path = reverse("bookings:verify_ticket", args=[booking.ticket_number])
    if request is not None:
        return request.build_absolute_uri(path)
    return f"http://127.0.0.1:8000{path}"


def ensure_ticket_qr(booking, request=None):
    """Create (or reuse) the ticket QR image and attach it to the booking."""
    if booking.qr_code and booking.qr_code.name and os.path.exists(booking.qr_code.path):
        return booking.qr_code
    if not booking.ticket_number:
        return None

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(_verify_url(booking, request))
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0B1F3A", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    filename = f"{booking.ticket_number}.png"
    booking.qr_code.save(filename, ContentFile(buffer.getvalue()), save=True)
    return booking.qr_code


def _inr(value):
    return f"Rs. {Decimal(value):,.2f}"


def build_ticket_pdf(booking, request=None):
    """Return an in-memory PDF boarding pass for a confirmed booking."""
    if booking.qr_code is None or not booking.qr_code.name:
        ensure_ticket_qr(booking, request)

    buffer = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"BUSGO E-Ticket {booking.ticket_number}")
    c.setAuthor("BUSGO Online Bus Booking")
    c.setSubject(f"{booking.route_text} on {booking.journey_date:%d %b %Y}")

    margin = 36
    inner_width = page_width - (margin * 2)

    # Background + decorative watermark
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
    c.saveState()
    c.setFillColor(HexColor("#EEF3FA"))
    c.setFont("Helvetica-Bold", 96)
    c.translate(page_width / 2, page_height / 2)
    c.rotate(32)
    c.drawCentredString(0, 0, "BUSGO")
    c.restoreState()

    # Header band
    header_height = 118
    c.setFillColor(NAVY)
    c.rect(0, page_height - header_height, page_width, header_height, fill=1, stroke=0)
    c.setFillColor(RED)
    c.rect(0, page_height - header_height, 10, header_height, fill=1, stroke=0)

    # Logo mark
    c.setFillColor(RED)
    c.roundRect(margin, page_height - 78, 40, 40, 9, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(margin + 20, page_height - 62, "BG")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 27)
    c.drawString(margin + 52, page_height - 68, "BUSGO")
    c.setFillColor(HexColor("#B9C7DB"))
    c.setFont("Helvetica", 9)
    c.drawString(margin + 53, page_height - 83, "ONLINE BUS BOOKING · YOUR JOURNEY, OUR PRIORITY")

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(page_width - margin, page_height - 50, "E-TICKET / BOARDING PASS")
    c.setFillColor(HexColor("#B9C7DB"))
    c.setFont("Helvetica", 8.5)
    c.drawRightString(page_width - margin, page_height - 65, f"Ticket No. {booking.ticket_number}")
    c.drawRightString(page_width - margin, page_height - 78, f"Booking ID {booking.booking_id}")

    # QR card
    qr_size = 112
    qr_x = page_width - margin - qr_size
    qr_y = page_height - header_height - 30
    c.setFillColor(white)
    c.setStrokeColor(HexColor("#DCE4F0"))
    c.roundRect(qr_x - 8, qr_y - 8, qr_size + 16, qr_size + 16, 10, fill=1, stroke=1)
    if booking.qr_code and os.path.exists(booking.qr_code.path):
        c.drawImage(
            ImageReader(booking.qr_code.path),
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )
    c.setFillColor(GREY)
    c.setFont("Helvetica", 7)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 20, "Scan to verify this ticket")

    # Journey summary
    y = page_height - header_height - 44
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, y, "JOURNEY")
    y -= 26
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 23)
    c.drawString(margin, y, booking.journey_source or booking.schedule.route.source)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin + 182, y, "→")
    c.setFillColor(NAVY)
    c.drawString(margin + 208, y, booking.journey_destination or booking.schedule.route.destination)

    y -= 26
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    date_text = booking.journey_date.strftime("%A, %d %B %Y")
    c.drawString(margin, y, date_text)
    c.drawString(margin + 208, y, booking.schedule.bus.operator.name)

    # Info boxes
    y -= 34
    box_gap = 10
    box_width = (inner_width - qr_size - 40 - (box_gap * 2)) / 3
    box_height = 58
    info = [
        ("DEPARTURE", booking.schedule.departure_time.strftime("%I:%M %p")),
        ("ARRIVAL", booking.schedule.arrival_time.strftime("%I:%M %p")),
        ("DURATION", booking.schedule.duration_display),
    ]
    for idx, (label, value) in enumerate(info):
        x = margin + idx * (box_width + box_gap)
        c.setFillColor(LIGHT)
        c.roundRect(x, y - box_height, box_width, box_height, 8, fill=1, stroke=0)
        c.setFillColor(GREY)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 12, y - 18, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 12, y - 38, value)

    # Bus details
    y -= box_height + 24
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "BUS DETAILS")
    c.setStrokeColor(HexColor("#E3EAF4"))
    c.line(margin, y - 6, page_width - margin, y - 6)
    y -= 24
    c.setFont("Helvetica", 9.5)
    c.setFillColor(GREY)
    c.drawString(margin, y, "Operator")
    c.drawString(margin + 180, y, "Bus")
    c.drawString(margin + 360, y, "Type")
    y -= 15
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(margin, y, booking.schedule.bus.operator.name[:28])
    c.drawString(margin + 180, y, booking.schedule.bus.name[:28])
    c.drawString(margin + 360, y, booking.schedule.bus.bus_type)

    # Passenger table
    y -= 36
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "PASSENGERS")
    y -= 8
    c.setStrokeColor(HexColor("#E3EAF4"))
    c.line(margin, y, page_width - margin, y)
    y -= 18

    headers = [("Seat", margin + 8), ("Passenger", margin + 64), ("Age", margin + 290), ("Gender", margin + 350), ("Status", margin + 440)]
    c.setFillColor(GREY)
    c.setFont("Helvetica-Bold", 8)
    for label, x in headers:
        c.drawString(x, y, label.upper())
    y -= 6
    c.line(margin, y, page_width - margin, y)
    y -= 18

    passengers = list(booking.passengers.select_related("booking_seat__seat"))
    if passengers:
        for p in passengers:
            c.setFillColor(NAVY)
            c.setFont("Helvetica-Bold", 9.5)
            c.drawString(margin + 8, y, p.seat_number)
            c.setFont("Helvetica", 9.5)
            c.drawString(margin + 64, y, p.name[:32])
            c.drawString(margin + 290, y, str(p.age))
            c.drawString(margin + 350, y, p.gender)
            c.setFillColor(GREEN)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(margin + 440, y, "CONFIRMED")
            y -= 19
            c.setStrokeColor(HexColor("#EEF2F8"))
            c.line(margin, y + 5, page_width - margin, y + 5)
    else:
        c.setFillColor(GREY)
        c.setFont("Helvetica", 9.5)
        c.drawString(margin + 8, y, "Passenger details will be available shortly.")
        y -= 20

    # Fare summary
    y -= 14
    summary_x = page_width - margin - 220
    c.setFillColor(LIGHT)
    c.roundRect(summary_x, y - 84, 220, 84, 8, fill=1, stroke=0)
    rows = [
        ("Seat fare", _inr(booking.seat_subtotal)),
        ("Convenience fee", _inr(booking.convenience_fee)),
        ("GST", _inr(booking.gst_amount)),
    ]
    row_y = y - 16
    for label, value in rows:
        c.setFillColor(GREY)
        c.setFont("Helvetica", 8)
        c.drawString(summary_x + 12, row_y, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 8.5)
        c.drawRightString(summary_x + 208, row_y, value)
        row_y -= 14
    c.setStrokeColor(HexColor("#DCE4F0"))
    c.line(summary_x + 12, row_y + 4, summary_x + 208, row_y + 4)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(summary_x + 12, row_y - 8, "TOTAL PAID")
    c.setFillColor(GREEN)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(summary_x + 208, row_y - 8, _inr(booking.total_amount))

    # Payment badge
    payment = booking.payments.filter(status="SUCCESS").order_by("-created_at").first()
    if not payment:
        payment = booking.payments.filter(status="REFUNDED").order_by("-created_at").first()
    c.setFillColor(GREEN if booking.status == "CONFIRMED" else RED)
    c.roundRect(margin, y - 38, 120, 24, 12, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    status_text = "PAYMENT SUCCESSFUL" if booking.status == "CONFIRMED" else booking.get_status_display().upper()
    c.drawCentredString(margin + 60, y - 30, status_text)

    # Footer
    c.setFillColor(NAVY)
    c.rect(0, 0, page_width, 66, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin, 46, "BUSGO · Your Journey, Our Priority")
    c.setFillColor(HexColor("#B9C7DB"))
    c.setFont("Helvetica", 7)
    c.drawString(margin, 34, f"Support: {settings.SITE_EMAIL} · {settings.SITE_PHONE} · {settings.SITE_ADDRESS}")
    c.drawString(margin, 23, "Carry a valid photo ID. Reach the boarding point 15 minutes before departure.")
    c.drawString(margin, 12, "This is a computer-generated ticket. Verify authenticity by scanning the QR code.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
