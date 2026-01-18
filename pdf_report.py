"""
PDF Report Generator for Security Incident Reports

Uses ReportLab to create professional PDF documents with:
- Header with logo placeholder and title
- Incident metadata section
- Executive summary
- Timeline with evidence
- Recommended actions
- Embedded video thumbnails (optional)
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os


class PDFReportGenerator:
    """Generates professional PDF reports from IncidentReport objects."""
    
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Create custom paragraph styles for the report."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a237e')
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#303f9f'),
            borderPadding=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='MetaLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666')
        ))
        
        self.styles.add(ParagraphStyle(
            name='MetaValue',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='BulletItem',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceBefore=3,
            spaceAfter=3
        ))
        
        self.styles.add(ParagraphStyle(
            name='TimelineTime',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1565c0')
        ))
        
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=TA_CENTER
        ))
    
    def generate(self, report) -> str:
        """Generate a PDF from an IncidentReport object.
        
        Args:
            report: IncidentReport dataclass instance
            
        Returns:
            Path to the generated PDF file
        """
        doc = SimpleDocTemplate(
            self.output_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        
        # Title
        story.append(Paragraph("SECURITY INCIDENT REPORT", self.styles['ReportTitle']))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a237e')))
        story.append(Spacer(1, 20))
        
        # Metadata table
        meta_data = [
            ["Incident Type:", report.incident_type],
            ["Location:", report.location or "Not specified"],
            ["Camera ID:", report.camera_id or "Not specified"],
            ["Time Range:", report.time_range],
            ["Report Generated:", report.created_at[:19].replace('T', ' ')]
        ]
        
        meta_table = Table(meta_data, colWidths=[1.5*inch, 4.5*inch])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 25))
        
        # Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Spacer(1, 10))
        
        for bullet in report.executive_summary:
            story.append(Paragraph(f"• {bullet}", self.styles['BulletItem']))
        
        story.append(Spacer(1, 20))
        
        # Timeline
        story.append(Paragraph("INCIDENT TIMELINE", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Spacer(1, 10))
        
        if report.timeline:
            timeline_data = [["Time", "Event", "Notes"]]
            for event in report.timeline:
                timeline_data.append([
                    event.get('time', ''),
                    event.get('event', ''),
                    event.get('notes', '') or ''
                ])
            
            timeline_table = Table(timeline_data, colWidths=[1*inch, 3.5*inch, 2*inch])
            timeline_table.setStyle(TableStyle([
                # Header row
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Data rows
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Alternating row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(timeline_table)
        else:
            story.append(Paragraph("No timeline events recorded.", self.styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Evidence Summary
        story.append(Paragraph("EVIDENCE SUMMARY", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Spacer(1, 10))
        
        if report.evidence:
            evidence_data = [["#", "Time Range", "Confidence", "Label"]]
            for i, ev in enumerate(report.evidence, 1):
                evidence_data.append([
                    str(i),
                    f"{ev.get('start_formatted', '')} - {ev.get('end_formatted', '')}",
                    f"{ev.get('confidence', 0):.0%}",
                    ev.get('label', '')[:40]
                ])
            
            evidence_table = Table(evidence_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 3.5*inch])
            evidence_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#303f9f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(evidence_table)
        else:
            story.append(Paragraph("No evidence clips included.", self.styles['Normal']))
        
        story.append(Spacer(1, 20))
        
        # Recommended Actions
        story.append(Paragraph("RECOMMENDED ACTIONS", self.styles['SectionHeader']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e0e0e0')))
        story.append(Spacer(1, 10))
        
        for i, action in enumerate(report.recommended_actions, 1):
            story.append(Paragraph(f"{i}. {action}", self.styles['BulletItem']))
        
        story.append(Spacer(1, 30))
        
        # Footer
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cccccc')))
        story.append(Spacer(1, 10))
        footer_text = f"Generated by Security Surveillance System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(footer_text, self.styles['Footer']))
        
        # Build PDF
        doc.build(story)
        return self.output_path


def generate_pdf_report(report, output_path: str) -> str:
    """Convenience function to generate a PDF report.
    
    Args:
        report: IncidentReport dataclass instance
        output_path: Where to save the PDF
        
    Returns:
        Path to the generated PDF file
    """
    generator = PDFReportGenerator(output_path)
    return generator.generate(report)
