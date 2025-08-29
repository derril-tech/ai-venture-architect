"""Export service for generating investor decks, product briefs, and data exports."""

import json
import csv
import io
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile

import structlog
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image as ReportLabImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from jinja2 import Environment, BaseLoader
import boto3
from botocore.exceptions import ClientError

from api.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ExportService:
    """Service for generating and managing exports."""
    
    def __init__(self):
        self.s3_client = None
        if settings.s3_access_key and settings.s3_secret_key:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=settings.s3_endpoint or None,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key
            )
        
        # Jinja2 environment for templates
        self.jinja_env = Environment(loader=BaseLoader())
        
        # PDF styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom PDF styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            textColor=HexColor('#2563eb'),
            alignment=TA_CENTER
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            textColor=HexColor('#1f2937')
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=12,
            textColor=HexColor('#374151'),
            borderWidth=1,
            borderColor=HexColor('#e5e7eb'),
            borderPadding=8
        ))
        
        # Metric style
        self.styles.add(ParagraphStyle(
            name='Metric',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=HexColor('#059669'),
            alignment=TA_CENTER
        ))
    
    async def export_investor_deck(
        self,
        ideas: List[Dict[str, Any]],
        workspace_info: Dict[str, Any],
        export_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate investor deck PDF."""
        
        config = export_config or {}
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            pdf_path = tmp_file.name
        
        try:
            # Generate PDF
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Title page
            story.extend(self._create_title_page(workspace_info, ideas))
            story.append(PageBreak())
            
            # Executive summary
            story.extend(self._create_executive_summary(ideas))
            story.append(PageBreak())
            
            # Market opportunity
            story.extend(self._create_market_opportunity_section(ideas))
            story.append(PageBreak())
            
            # Product concepts
            for i, idea in enumerate(ideas[:5]):  # Limit to top 5 ideas
                story.extend(self._create_product_section(idea, i + 1))
                if i < len(ideas) - 1:
                    story.append(PageBreak())
            
            # Business model
            story.append(PageBreak())
            story.extend(self._create_business_model_section(ideas))
            
            # Competitive analysis
            story.append(PageBreak())
            story.extend(self._create_competitive_section(ideas))
            
            # Financial projections
            story.append(PageBreak())
            story.extend(self._create_financial_section(ideas))
            
            # Appendix
            story.append(PageBreak())
            story.extend(self._create_appendix(ideas))
            
            # Build PDF
            doc.build(story)
            
            # Upload to S3 if configured
            s3_url = None
            if self.s3_client:
                s3_key = f"exports/investor-deck-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.pdf"
                s3_url = await self._upload_to_s3(pdf_path, s3_key)
            
            # Get file size
            file_size = Path(pdf_path).stat().st_size
            
            return {
                "type": "investor_deck",
                "format": "pdf",
                "file_path": pdf_path,
                "s3_url": s3_url,
                "file_size": file_size,
                "page_count": len(story),
                "generated_at": datetime.utcnow().isoformat(),
                "ideas_included": len(ideas)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate investor deck: {e}")
            # Clean up temp file
            try:
                Path(pdf_path).unlink()
            except:
                pass
            raise
    
    async def export_product_brief(
        self,
        idea: Dict[str, Any],
        export_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate detailed product brief PDF."""
        
        config = export_config or {}
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            pdf_path = tmp_file.name
        
        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            story = []
            
            # Title
            story.append(Paragraph(f"Product Brief: {idea.get('title', 'Untitled')}", self.styles['CustomTitle']))
            story.append(Spacer(1, 20))
            
            # Overview
            story.append(Paragraph("Product Overview", self.styles['SectionHeader']))
            story.append(Paragraph(idea.get('description', 'No description available'), self.styles['Normal']))
            story.append(Spacer(1, 15))
            
            # Value proposition
            if idea.get('uvp'):
                story.append(Paragraph("Unique Value Proposition", self.styles['SectionHeader']))
                story.append(Paragraph(idea['uvp'], self.styles['Normal']))
                story.append(Spacer(1, 15))
            
            # Problem & solution
            if idea.get('problem_statement'):
                story.append(Paragraph("Problem Statement", self.styles['SectionHeader']))
                story.append(Paragraph(idea['problem_statement'], self.styles['Normal']))
                story.append(Spacer(1, 15))
            
            if idea.get('solution_approach'):
                story.append(Paragraph("Solution Approach", self.styles['SectionHeader']))
                story.append(Paragraph(idea['solution_approach'], self.styles['Normal']))
                story.append(Spacer(1, 15))
            
            # Target market
            story.extend(self._create_target_market_section(idea))
            
            # Product features
            story.extend(self._create_features_section(idea))
            
            # Business model
            story.extend(self._create_idea_business_model(idea))
            
            # Technical details
            story.extend(self._create_technical_section(idea))
            
            # Risks and mitigation
            story.extend(self._create_risks_section(idea))
            
            # Sources and citations
            story.extend(self._create_sources_section(idea))
            
            doc.build(story)
            
            # Upload to S3 if configured
            s3_url = None
            if self.s3_client:
                s3_key = f"exports/product-brief-{idea.get('id', 'unknown')}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.pdf"
                s3_url = await self._upload_to_s3(pdf_path, s3_key)
            
            file_size = Path(pdf_path).stat().st_size
            
            return {
                "type": "product_brief",
                "format": "pdf",
                "file_path": pdf_path,
                "s3_url": s3_url,
                "file_size": file_size,
                "generated_at": datetime.utcnow().isoformat(),
                "idea_id": idea.get('id')
            }
            
        except Exception as e:
            logger.error(f"Failed to generate product brief: {e}")
            try:
                Path(pdf_path).unlink()
            except:
                pass
            raise
    
    async def export_csv_data(
        self,
        ideas: List[Dict[str, Any]],
        export_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Export ideas data as CSV."""
        
        config = export_config or {}
        fields = config.get('fields', [
            'id', 'title', 'description', 'uvp', 'attractiveness_score',
            'confidence_score', 'status', 'created_at'
        ])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as tmp_file:
            csv_path = tmp_file.name
            writer = csv.DictWriter(tmp_file, fieldnames=fields)
            
            # Write header
            writer.writeheader()
            
            # Write data
            for idea in ideas:
                row = {}
                for field in fields:
                    value = idea.get(field, '')
                    # Handle complex fields
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    row[field] = value
                writer.writerow(row)
        
        # Upload to S3 if configured
        s3_url = None
        if self.s3_client:
            s3_key = f"exports/ideas-data-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
            s3_url = await self._upload_to_s3(csv_path, s3_key)
        
        file_size = Path(csv_path).stat().st_size
        
        return {
            "type": "csv_export",
            "format": "csv",
            "file_path": csv_path,
            "s3_url": s3_url,
            "file_size": file_size,
            "generated_at": datetime.utcnow().isoformat(),
            "record_count": len(ideas),
            "fields": fields
        }
    
    async def export_json_bundle(
        self,
        ideas: List[Dict[str, Any]],
        workspace_info: Dict[str, Any],
        export_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Export complete data bundle as JSON."""
        
        bundle = {
            "export_info": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "workspace": workspace_info,
                "total_ideas": len(ideas)
            },
            "ideas": ideas,
            "metadata": {
                "export_config": export_config or {},
                "schema_version": "1.0"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json_path = tmp_file.name
            json.dump(bundle, tmp_file, indent=2, default=str)
        
        # Upload to S3 if configured
        s3_url = None
        if self.s3_client:
            s3_key = f"exports/data-bundle-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
            s3_url = await self._upload_to_s3(json_path, s3_key)
        
        file_size = Path(json_path).stat().st_size
        
        return {
            "type": "json_bundle",
            "format": "json",
            "file_path": json_path,
            "s3_url": s3_url,
            "file_size": file_size,
            "generated_at": datetime.utcnow().isoformat(),
            "ideas_count": len(ideas)
        }
    
    async def export_notion_page(
        self,
        idea: Dict[str, Any],
        export_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Notion-compatible markdown."""
        
        # Create Notion-style markdown
        markdown_content = self._generate_notion_markdown(idea)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp_file:
            md_path = tmp_file.name
            tmp_file.write(markdown_content)
        
        # Upload to S3 if configured
        s3_url = None
        if self.s3_client:
            s3_key = f"exports/notion-{idea.get('id', 'unknown')}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.md"
            s3_url = await self._upload_to_s3(md_path, s3_key)
        
        file_size = Path(md_path).stat().st_size
        
        return {
            "type": "notion_page",
            "format": "markdown",
            "file_path": md_path,
            "s3_url": s3_url,
            "file_size": file_size,
            "generated_at": datetime.utcnow().isoformat(),
            "idea_id": idea.get('id'),
            "content": markdown_content
        }
    
    # PDF section generators
    def _create_title_page(self, workspace_info: Dict[str, Any], ideas: List[Dict[str, Any]]) -> List:
        """Create title page for investor deck."""
        story = []
        
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("AI Venture Architect", self.styles['CustomTitle']))
        story.append(Paragraph("Product Opportunity Analysis", self.styles['Subtitle']))
        story.append(Spacer(1, 0.5*inch))
        
        story.append(Paragraph(f"Workspace: {workspace_info.get('name', 'Unknown')}", self.styles['Normal']))
        story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%B %d, %Y')}", self.styles['Normal']))
        story.append(Paragraph(f"Ideas Analyzed: {len(ideas)}", self.styles['Normal']))
        
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("Confidential & Proprietary", self.styles['Normal']))
        
        return story
    
    def _create_executive_summary(self, ideas: List[Dict[str, Any]]) -> List:
        """Create executive summary section."""
        story = []
        
        story.append(Paragraph("Executive Summary", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Key metrics
        avg_attractiveness = sum(idea.get('attractiveness_score', 0) for idea in ideas) / len(ideas) if ideas else 0
        avg_confidence = sum(idea.get('confidence_score', 0) for idea in ideas) / len(ideas) if ideas else 0
        
        summary_text = f"""
        This analysis presents {len(ideas)} validated product opportunities identified through 
        AI-powered market research and competitive intelligence. The opportunities span multiple 
        industries and market segments, with an average attractiveness score of {avg_attractiveness:.1f}/10 
        and confidence score of {avg_confidence:.1f}/10.
        
        Key highlights include emerging trends in AI/ML, fintech innovation, and productivity tools. 
        Each opportunity has been analyzed for market size, competitive positioning, technical 
        feasibility, and business model viability.
        """
        
        story.append(Paragraph(summary_text, self.styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Top opportunities table
        if ideas:
            story.append(Paragraph("Top Opportunities", self.styles['SectionHeader']))
            
            table_data = [['Rank', 'Product Concept', 'Attractiveness', 'Confidence']]
            
            sorted_ideas = sorted(ideas, key=lambda x: x.get('attractiveness_score', 0), reverse=True)
            for i, idea in enumerate(sorted_ideas[:5]):
                table_data.append([
                    str(i + 1),
                    idea.get('title', 'Untitled')[:40] + ('...' if len(idea.get('title', '')) > 40 else ''),
                    f"{idea.get('attractiveness_score', 0):.1f}/10",
                    f"{idea.get('confidence_score', 0):.1f}/10"
                ])
            
            table = Table(table_data, colWidths=[0.5*inch, 3*inch, 1*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), HexColor('#ffffff')),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb'))
            ]))
            
            story.append(table)
        
        return story
    
    def _create_market_opportunity_section(self, ideas: List[Dict[str, Any]]) -> List:
        """Create market opportunity section."""
        story = []
        
        story.append(Paragraph("Market Opportunity", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Aggregate market data
        total_tam = sum(
            idea.get('tam_sam_som', {}).get('tam', 0) 
            for idea in ideas
        )
        
        industries = set()
        for idea in ideas:
            industries.update(idea.get('target_segments', []))
        
        market_text = f"""
        The identified opportunities represent a combined Total Addressable Market (TAM) of 
        ${total_tam:,.0f}M across {len(industries)} key industry segments.
        
        Key market trends driving these opportunities include:
        • Digital transformation acceleration
        • AI/ML adoption across industries  
        • Remote work and productivity tools demand
        • Fintech and embedded finance growth
        • Healthcare digitization
        """
        
        story.append(Paragraph(market_text, self.styles['Normal']))
        
        return story
    
    def _create_product_section(self, idea: Dict[str, Any], rank: int) -> List:
        """Create product section for an idea."""
        story = []
        
        story.append(Paragraph(f"Opportunity #{rank}: {idea.get('title', 'Untitled')}", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Overview
        story.append(Paragraph("Overview", self.styles['SectionHeader']))
        story.append(Paragraph(idea.get('description', 'No description available'), self.styles['Normal']))
        story.append(Spacer(1, 15))
        
        # Key metrics
        metrics_data = [
            ['Metric', 'Value'],
            ['Attractiveness Score', f"{idea.get('attractiveness_score', 0):.1f}/10"],
            ['Confidence Score', f"{idea.get('confidence_score', 0):.1f}/10"],
            ['Market Size (TAM)', f"${idea.get('tam_sam_som', {}).get('tam', 0):,.0f}M"],
            ['Status', idea.get('status', 'Unknown')]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f3f4f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#1f2937')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb'))
        ]))
        
        story.append(metrics_table)
        story.append(Spacer(1, 15))
        
        # Value proposition
        if idea.get('uvp'):
            story.append(Paragraph("Value Proposition", self.styles['SectionHeader']))
            story.append(Paragraph(idea['uvp'], self.styles['Normal']))
            story.append(Spacer(1, 15))
        
        # MVP features
        if idea.get('mvp_features'):
            story.append(Paragraph("Key Features", self.styles['SectionHeader']))
            for feature in idea['mvp_features'][:5]:
                story.append(Paragraph(f"• {feature}", self.styles['Normal']))
            story.append(Spacer(1, 15))
        
        return story
    
    def _create_business_model_section(self, ideas: List[Dict[str, Any]]) -> List:
        """Create business model section."""
        story = []
        
        story.append(Paragraph("Business Models", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Revenue model distribution
        revenue_models = {}
        for idea in ideas:
            model = idea.get('pricing_model', 'Unknown')
            revenue_models[model] = revenue_models.get(model, 0) + 1
        
        story.append(Paragraph("Revenue Model Distribution", self.styles['SectionHeader']))
        for model, count in revenue_models.items():
            story.append(Paragraph(f"• {model}: {count} opportunities", self.styles['Normal']))
        
        return story
    
    def _create_competitive_section(self, ideas: List[Dict[str, Any]]) -> List:
        """Create competitive analysis section."""
        story = []
        
        story.append(Paragraph("Competitive Landscape", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        competitive_text = """
        The competitive analysis reveals several key insights:
        
        • Market fragmentation creates opportunities for consolidation
        • Emerging technologies enable new business models
        • Customer pain points remain unaddressed by existing solutions
        • Pricing gaps exist in multiple market segments
        """
        
        story.append(Paragraph(competitive_text, self.styles['Normal']))
        
        return story
    
    def _create_financial_section(self, ideas: List[Dict[str, Any]]) -> List:
        """Create financial projections section."""
        story = []
        
        story.append(Paragraph("Financial Projections", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Aggregate financial data
        total_som = sum(
            idea.get('tam_sam_som', {}).get('som', 0) 
            for idea in ideas
        )
        
        financial_text = f"""
        Combined Serviceable Obtainable Market (SOM): ${total_som:,.0f}M
        
        Revenue projections are based on conservative market penetration assumptions
        and validated pricing models. Each opportunity has been assessed for:
        
        • Customer acquisition costs (CAC)
        • Lifetime value (LTV) 
        • Unit economics and scalability
        • Funding requirements
        """
        
        story.append(Paragraph(financial_text, self.styles['Normal']))
        
        return story
    
    def _create_appendix(self, ideas: List[Dict[str, Any]]) -> List:
        """Create appendix section."""
        story = []
        
        story.append(Paragraph("Appendix", self.styles['CustomTitle']))
        story.append(Spacer(1, 20))
        
        # Methodology
        story.append(Paragraph("Methodology", self.styles['SectionHeader']))
        methodology_text = """
        This analysis was generated using AI Venture Architect's multi-agent system:
        
        • Market Research Agent: Analyzed market signals and trends
        • Competitive Intelligence Agent: Assessed competitive landscape  
        • Product Ideation Agent: Generated and refined product concepts
        • Business Validation Agent: Evaluated business model viability
        • Technical Assessment Agent: Analyzed implementation feasibility
        
        All recommendations are based on real market data and validated assumptions.
        """
        
        story.append(Paragraph(methodology_text, self.styles['Normal']))
        
        return story
    
    # Helper methods for product brief sections
    def _create_target_market_section(self, idea: Dict[str, Any]) -> List:
        """Create target market section for product brief."""
        story = []
        
        if idea.get('icps') or idea.get('target_segments'):
            story.append(Paragraph("Target Market", self.styles['SectionHeader']))
            
            if idea.get('target_segments'):
                story.append(Paragraph("Target Segments:", self.styles['Normal']))
                for segment in idea['target_segments']:
                    story.append(Paragraph(f"• {segment}", self.styles['Normal']))
                story.append(Spacer(1, 10))
            
            if idea.get('icps'):
                story.append(Paragraph("Ideal Customer Profiles:", self.styles['Normal']))
                for profile_type, profile_desc in idea['icps'].items():
                    story.append(Paragraph(f"• {profile_type}: {profile_desc}", self.styles['Normal']))
                story.append(Spacer(1, 15))
        
        return story
    
    def _create_features_section(self, idea: Dict[str, Any]) -> List:
        """Create features section for product brief."""
        story = []
        
        if idea.get('mvp_features'):
            story.append(Paragraph("Product Features", self.styles['SectionHeader']))
            story.append(Paragraph("MVP Features:", self.styles['Normal']))
            for feature in idea['mvp_features']:
                story.append(Paragraph(f"• {feature}", self.styles['Normal']))
            story.append(Spacer(1, 15))
        
        return story
    
    def _create_idea_business_model(self, idea: Dict[str, Any]) -> List:
        """Create business model section for individual idea."""
        story = []
        
        story.append(Paragraph("Business Model", self.styles['SectionHeader']))
        
        if idea.get('pricing_model'):
            story.append(Paragraph(f"Pricing Model: {idea['pricing_model']}", self.styles['Normal']))
        
        if idea.get('tam_sam_som'):
            tam_sam_som = idea['tam_sam_som']
            story.append(Paragraph("Market Size:", self.styles['Normal']))
            story.append(Paragraph(f"• TAM: ${tam_sam_som.get('tam', 0):,.0f}M", self.styles['Normal']))
            story.append(Paragraph(f"• SAM: ${tam_sam_som.get('sam', 0):,.0f}M", self.styles['Normal']))
            story.append(Paragraph(f"• SOM: ${tam_sam_som.get('som', 0):,.0f}M", self.styles['Normal']))
        
        story.append(Spacer(1, 15))
        return story
    
    def _create_technical_section(self, idea: Dict[str, Any]) -> List:
        """Create technical section for product brief."""
        story = []
        
        if idea.get('tech_stack') or idea.get('technical_risks'):
            story.append(Paragraph("Technical Details", self.styles['SectionHeader']))
            
            if idea.get('tech_stack'):
                story.append(Paragraph("Technology Stack:", self.styles['Normal']))
                tech_stack = idea['tech_stack']
                for category, technologies in tech_stack.items():
                    if isinstance(technologies, list):
                        tech_list = ', '.join(technologies)
                    else:
                        tech_list = str(technologies)
                    story.append(Paragraph(f"• {category}: {tech_list}", self.styles['Normal']))
                story.append(Spacer(1, 10))
            
            if idea.get('technical_risks'):
                story.append(Paragraph("Technical Risks:", self.styles['Normal']))
                for risk in idea['technical_risks']:
                    story.append(Paragraph(f"• {risk}", self.styles['Normal']))
                story.append(Spacer(1, 15))
        
        return story
    
    def _create_risks_section(self, idea: Dict[str, Any]) -> List:
        """Create risks section for product brief."""
        story = []
        
        if idea.get('risks') or idea.get('compliance_notes'):
            story.append(Paragraph("Risks & Compliance", self.styles['SectionHeader']))
            
            if idea.get('risks'):
                story.append(Paragraph("Business Risks:", self.styles['Normal']))
                risks = idea['risks']
                for risk_category, risk_items in risks.items():
                    if isinstance(risk_items, list):
                        for risk_item in risk_items:
                            story.append(Paragraph(f"• {risk_category}: {risk_item}", self.styles['Normal']))
                    else:
                        story.append(Paragraph(f"• {risk_category}: {risk_items}", self.styles['Normal']))
                story.append(Spacer(1, 10))
            
            if idea.get('compliance_notes'):
                story.append(Paragraph("Compliance Requirements:", self.styles['Normal']))
                for note in idea['compliance_notes']:
                    story.append(Paragraph(f"• {note}", self.styles['Normal']))
                story.append(Spacer(1, 15))
        
        return story
    
    def _create_sources_section(self, idea: Dict[str, Any]) -> List:
        """Create sources section for product brief."""
        story = []
        
        if idea.get('sources') or idea.get('citations'):
            story.append(Paragraph("Sources & Citations", self.styles['SectionHeader']))
            
            if idea.get('citations'):
                story.append(Paragraph("Analysis Sources:", self.styles['Normal']))
                for source_type, citation in idea['citations'].items():
                    story.append(Paragraph(f"• {source_type}: {citation}", self.styles['Normal']))
                story.append(Spacer(1, 10))
            
            if idea.get('sources'):
                story.append(Paragraph(f"Data Sources: {len(idea['sources'])} market signals analyzed", self.styles['Normal']))
                story.append(Spacer(1, 15))
        
        return story
    
    def _generate_notion_markdown(self, idea: Dict[str, Any]) -> str:
        """Generate Notion-compatible markdown for an idea."""
        
        markdown = f"""# {idea.get('title', 'Untitled Product Idea')}

## Overview
{idea.get('description', 'No description available')}

## Unique Value Proposition
{idea.get('uvp', 'Not defined')}

## Problem & Solution
### Problem Statement
{idea.get('problem_statement', 'Not defined')}

### Solution Approach  
{idea.get('solution_approach', 'Not defined')}

## Target Market
"""
        
        if idea.get('target_segments'):
            markdown += "### Target Segments\n"
            for segment in idea['target_segments']:
                markdown += f"- {segment}\n"
            markdown += "\n"
        
        if idea.get('icps'):
            markdown += "### Ideal Customer Profiles\n"
            for profile_type, profile_desc in idea['icps'].items():
                markdown += f"- **{profile_type}**: {profile_desc}\n"
            markdown += "\n"
        
        if idea.get('mvp_features'):
            markdown += "## Product Features\n### MVP Features\n"
            for feature in idea['mvp_features']:
                markdown += f"- {feature}\n"
            markdown += "\n"
        
        if idea.get('tam_sam_som'):
            tam_sam_som = idea['tam_sam_som']
            markdown += f"""## Market Size
- **TAM**: ${tam_sam_som.get('tam', 0):,.0f}M
- **SAM**: ${tam_sam_som.get('sam', 0):,.0f}M  
- **SOM**: ${tam_sam_som.get('som', 0):,.0f}M

"""
        
        markdown += f"""## Metrics
- **Attractiveness Score**: {idea.get('attractiveness_score', 0):.1f}/10
- **Confidence Score**: {idea.get('confidence_score', 0):.1f}/10
- **Status**: {idea.get('status', 'Unknown')}

## Generated
- **Created**: {idea.get('created_at', 'Unknown')}
- **AI Analysis**: Multi-agent market research and validation
"""
        
        return markdown
    
    async def _upload_to_s3(self, file_path: str, s3_key: str) -> Optional[str]:
        """Upload file to S3 and return URL."""
        if not self.s3_client:
            return None
        
        try:
            self.s3_client.upload_file(file_path, settings.s3_bucket, s3_key)
            
            # Generate presigned URL (valid for 7 days)
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.s3_bucket, 'Key': s3_key},
                ExpiresIn=7*24*3600  # 7 days
            )
            
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload to S3: {e}")
            return None


# Global service instance
export_service = ExportService()
