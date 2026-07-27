import io
from datetime import date
from uuid import UUID

from sqlalchemy import select, func, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.db.models.reflections import Reflection
from app.db.models.goal_streaks import GoalStreak
from app.db.models.pod_members import PodMember
from app.db.models.user import User
from app.db.models.pods import Pod

class ReportsService:
    async def generate_pod_report_pdf(
        self,
        db: AsyncSession,
        pod_id: UUID,
        user: User,
        start_date: date,
        end_date: date
    ) -> bytes:
        # 1. Verify user is in the pod
        member = await db.scalar(
            select(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.user_id == user.id,
                PodMember.is_active.is_(True),
            )
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a pod member")

        pod = await db.scalar(select(Pod).where(Pod.id == pod_id))
        if not pod:
            raise HTTPException(status_code=404, detail="Pod not found")

        # 2. Fetch all members
        members = await db.scalars(
            select(User).join(PodMember).where(
                PodMember.pod_id == pod_id,
                PodMember.is_active.is_(True)
            )
        )
        members_list = members.all()

        user_names = []
        checkins_data = []
        streaks_data = []

        table_data = [["User", "Check-ins", "Max Streak"]]

        # 3. Calculate stats for each user
        for m in members_list:
            user_names.append(m.name or "Unknown")

            # Checkins in date range
            checkins = await db.scalar(
                select(func.count(Reflection.id)).where(
                    Reflection.pod_id == pod_id,
                    Reflection.user_id == m.id,
                    Reflection.reflection_date.between(start_date, end_date),
                )
            ) or 0
            checkins_data.append(checkins)

            # Max streak in pod (for simplicity we take max of their current streaks)
            max_streak = await db.scalar(
                select(func.max(GoalStreak.current_streak))
                .where(GoalStreak.user_id == m.id)
            ) or 0
            streaks_data.append(max_streak)

            table_data.append([m.name or "Unknown", str(checkins), str(max_streak)])

        # 4. Generate matplotlib chart
        fig, ax = plt.subplots(figsize=(8, 4))
        x = range(len(user_names))
        
        ax.bar([i - 0.2 for i in x], checkins_data, width=0.4, label='Check-ins', color='#4f46e5')
        ax.bar([i + 0.2 for i in x], streaks_data, width=0.4, label='Max Streak', color='#10b981')
        
        ax.set_ylabel('Count')
        ax.set_title('Pod Member Performance')
        ax.set_xticks(x)
        ax.set_xticklabels(user_names, rotation=45, ha='right')
        ax.legend()
        
        plt.tight_layout()
        
        chart_buffer = io.BytesIO()
        plt.savefig(chart_buffer, format='png', dpi=150)
        chart_buffer.seek(0)
        plt.close(fig)

        # 5. Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1e3a8a')
        )
        elements.append(Paragraph(f"Pod Performance Report", title_style))
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            textColor=colors.gray
        )
        elements.append(Paragraph(f"<b>Pod:</b> {pod.name}", subtitle_style))
        elements.append(Paragraph(f"<b>Date Range:</b> {start_date} to {end_date}", subtitle_style))
        elements.append(Spacer(1, 20))

        # Add Chart
        img = Image(chart_buffer, width=500, height=250)
        elements.append(img)
        elements.append(Spacer(1, 30))

        # Add Table
        t = Table(table_data, colWidths=[200, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.white)
        ]))
        elements.append(t)

        # Build PDF
        doc.build(elements)
        
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()

reports_service = ReportsService()
