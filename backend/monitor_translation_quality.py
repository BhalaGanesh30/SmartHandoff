"""
Translation Quality Monitoring Script (US-027 TASK-004)

Monitors patient instructions translation quality in production:
- Back-translation similarity scores
- Quality check pass rates  
- FK grade distributions
- Error rates and failure patterns

Usage:
    python monitor_translation_quality.py --days 7
    python monitor_translation_quality.py --encounter-id enc-12345
"""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Placeholder imports - adjust based on your ORM setup
# from app.models import PatientInstructionsDocument
# from app.db.session import AsyncSession


class TranslationQualityMonitor:
    """
    Monitor translation quality metrics from production data.
    
    Tracks:
    - Similarity score distribution per language
    - Quality check pass/fail rates
    - FK grade ranges
    - Error patterns
    """
    
    def __init__(self):
        self.metrics = {
            "total_documents": 0,
            "languages": defaultdict(lambda: {
                "count": 0,
                "quality_passed": 0,
                "quality_failed": 0,
                "similarities": [],
                "fk_grades": [],
            }),
            "errors": [],
        }
    
    def analyze_document(self, translations: Dict) -> None:
        """
        Analyze a single PatientInstructionsDocument's translations.
        
        Args:
            translations: Dict mapping language codes to TranslationEntry objects
        """
        self.metrics["total_documents"] += 1
        
        for lang_code, entry in translations.items():
            if lang_code == "en":
                continue  # Skip English base
            
            lang_metrics = self.metrics["languages"][lang_code]
            lang_metrics["count"] += 1
            
            # Quality check tracking
            if entry.quality_check_passed:
                lang_metrics["quality_passed"] += 1
            else:
                lang_metrics["quality_failed"] += 1
                
                # Log quality failure details
                self.metrics["errors"].append({
                    "language": lang_code,
                    "issue": "quality_check_failed",
                    "similarity": entry.back_translation_similarity,
                })
            
            # Similarity score tracking
            if entry.back_translation_similarity is not None:
                lang_metrics["similarities"].append(entry.back_translation_similarity)
            
            # FK grade tracking
            if entry.flesch_kincaid_grade is not None:
                lang_metrics["fk_grades"].append(entry.flesch_kincaid_grade)
    
    def generate_report(self) -> str:
        """
        Generate comprehensive quality report.
        
        Returns:
            Formatted report string
        """
        report_lines = [
            "=" * 80,
            "PATIENT INSTRUCTIONS TRANSLATION QUALITY REPORT",
            "=" * 80,
            "",
            f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Documents Analyzed: {self.metrics['total_documents']}",
            "",
            "QUALITY METRICS BY LANGUAGE",
            "-" * 80,
        ]
        
        for lang_code in ["es", "fr", "zh", "pt"]:
            lang_metrics = self.metrics["languages"][lang_code]
            
            if lang_metrics["count"] == 0:
                report_lines.append(f"\n{lang_code.upper()}: No data")
                continue
            
            # Calculate statistics
            total = lang_metrics["count"]
            passed = lang_metrics["quality_passed"]
            failed = lang_metrics["quality_failed"]
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            similarities = lang_metrics["similarities"]
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0
            min_similarity = min(similarities) if similarities else 0
            
            fk_grades = lang_metrics["fk_grades"]
            avg_fk = sum(fk_grades) / len(fk_grades) if fk_grades else 0
            max_fk = max(fk_grades) if fk_grades else 0
            
            # Language section
            report_lines.extend([
                "",
                f"{lang_code.upper()} (Spanish)" if lang_code == "es" else 
                f"{lang_code.upper()} (French)" if lang_code == "fr" else
                f"{lang_code.upper()} (Chinese)" if lang_code == "zh" else
                f"{lang_code.upper()} (Portuguese)",
                f"  Total Translations: {total}",
                f"  Quality Check Pass Rate: {pass_rate:.1f}% ({passed}/{total})",
                f"  Quality Check Failures: {failed}",
                "",
                f"  Back-Translation Similarity:",
                f"    Average: {avg_similarity:.3f}",
                f"    Minimum: {min_similarity:.3f}",
                f"    {'✓' if avg_similarity >= 0.85 else '✗'} Threshold: 0.85",
                "",
                f"  Flesch-Kincaid Grade:",
                f"    Average: {avg_fk:.2f}",
                f"    Maximum: {max_fk:.2f}",
                f"    {'✓' if avg_fk <= 10.0 else '✗'} Target: ≤ 10.0",
            ])
        
        # Error summary
        report_lines.extend([
            "",
            "ERROR SUMMARY",
            "-" * 80,
            f"Total Quality Check Failures: {len(self.metrics['errors'])}",
        ])
        
        if self.metrics["errors"]:
            # Group errors by language
            errors_by_lang = defaultdict(int)
            for error in self.metrics["errors"]:
                errors_by_lang[error["language"]] += 1
            
            report_lines.append("")
            report_lines.append("Failures by Language:")
            for lang_code, count in sorted(errors_by_lang.items()):
                report_lines.append(f"  {lang_code}: {count} failures")
            
            # Show worst similarity scores
            report_lines.append("")
            report_lines.append("Lowest Similarity Scores (< 0.85):")
            low_similarity_errors = [
                e for e in self.metrics["errors"]
                if e.get("similarity") is not None and e["similarity"] < 0.85
            ]
            low_similarity_errors.sort(key=lambda x: x["similarity"])
            
            for error in low_similarity_errors[:5]:  # Top 5 worst
                report_lines.append(
                    f"  {error['language']}: {error['similarity']:.3f}"
                )
        else:
            report_lines.append("  No quality check failures! ✓")
        
        # Recommendations
        report_lines.extend([
            "",
            "RECOMMENDATIONS",
            "-" * 80,
        ])
        
        recommendations = []
        
        # Check overall pass rate
        total_translations = sum(
            m["count"] for m in self.metrics["languages"].values()
        )
        total_passed = sum(
            m["quality_passed"] for m in self.metrics["languages"].values()
        )
        overall_pass_rate = (total_passed / total_translations * 100) if total_translations > 0 else 0
        
        if overall_pass_rate < 90:
            recommendations.append(
                f"⚠ Overall pass rate ({overall_pass_rate:.1f}%) is below 90%. "
                "Consider reviewing translation prompts or adjusting similarity threshold."
            )
        
        # Check per-language issues
        for lang_code, lang_metrics in self.metrics["languages"].items():
            if lang_metrics["count"] == 0:
                continue
            
            lang_pass_rate = (
                lang_metrics["quality_passed"] / lang_metrics["count"] * 100
            )
            
            if lang_pass_rate < 85:
                lang_name = {
                    "es": "Spanish", "fr": "French", 
                    "zh": "Chinese", "pt": "Portuguese"
                }.get(lang_code, lang_code)
                
                recommendations.append(
                    f"⚠ {lang_name} pass rate ({lang_pass_rate:.1f}%) is low. "
                    "Consider language-specific prompt optimization."
                )
        
        # Check FK grades
        for lang_code, lang_metrics in self.metrics["languages"].items():
            if not lang_metrics["fk_grades"]:
                continue
            
            avg_fk = sum(lang_metrics["fk_grades"]) / len(lang_metrics["fk_grades"])
            
            if avg_fk > 10.0:
                lang_name = {
                    "es": "Spanish", "fr": "French",
                    "zh": "Chinese", "pt": "Portuguese"
                }.get(lang_code, lang_code)
                
                recommendations.append(
                    f"⚠ {lang_name} average FK grade ({avg_fk:.2f}) exceeds 10.0. "
                    "Translations may be too complex for target reading level."
                )
        
        if not recommendations:
            recommendations.append("✓ All quality metrics within acceptable ranges.")
        
        report_lines.extend(recommendations)
        
        report_lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(report_lines)


async def fetch_documents_from_db(
    days: Optional[int] = None,
    encounter_id: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch patient instructions documents from database.
    
    Args:
        days: Number of days to look back
        encounter_id: Specific encounter ID to analyze
    
    Returns:
        List of document translations dictionaries
    
    Note: This is a placeholder - implement based on your ORM/database setup.
    """
    # TODO: Implement database query
    # Example:
    # async with AsyncSession() as session:
    #     query = select(PatientInstructionsDocument)
    #     
    #     if days:
    #         cutoff_date = datetime.now() - timedelta(days=days)
    #         query = query.where(PatientInstructionsDocument.created_at >= cutoff_date)
    #     
    #     if encounter_id:
    #         query = query.where(PatientInstructionsDocument.encounter_id == encounter_id)
    #     
    #     result = await session.execute(query)
    #     documents = result.scalars().all()
    #     
    #     return [doc.translations for doc in documents]
    
    # Placeholder return
    print("⚠ Database fetch not implemented - returning sample data")
    
    # Sample data for demonstration
    from agents.documentation.patient_instructions_schemas import (
        PatientInstructionsContent,
        TranslationEntry,
    )
    
    sample_translations = {
        "en": TranslationEntry(
            language_code="en",
            content=PatientInstructionsContent(
                home_care_instructions="Rest at home",
                medications="Take medicine",
                warning_signs="Call doctor",
                follow_up_appointments="See doctor",
                diet_and_activity="Eat healthy",
                emergency_contact="Call 911",
            ),
            back_translation_similarity=None,
            quality_check_passed=True,
            flesch_kincaid_grade=7.2,
        ),
        "es": TranslationEntry(
            language_code="es",
            content=PatientInstructionsContent(
                home_care_instructions="Descansa en casa",
                medications="Toma medicina",
                warning_signs="Llama al doctor",
                follow_up_appointments="Ve al doctor",
                diet_and_activity="Come sano",
                emergency_contact="Llama al 911",
            ),
            back_translation_similarity=0.88,
            quality_check_passed=True,
            flesch_kincaid_grade=8.1,
        ),
        "fr": TranslationEntry(
            language_code="fr",
            content=PatientInstructionsContent(
                home_care_instructions="Reposez-vous",
                medications="Prenez médicament",
                warning_signs="Appelez docteur",
                follow_up_appointments="Voir docteur",
                diet_and_activity="Mangez sain",
                emergency_contact="Appelez 911",
            ),
            back_translation_similarity=0.82,
            quality_check_passed=False,
            flesch_kincaid_grade=9.3,
        ),
    }
    
    return [sample_translations]


async def main():
    """Main entry point for translation quality monitoring."""
    parser = argparse.ArgumentParser(
        description="Monitor patient instructions translation quality"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--encounter-id",
        type=str,
        help="Analyze specific encounter ID",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save report to file (default: print to stdout)",
    )
    
    args = parser.parse_args()
    
    print(f"Fetching translation data (last {args.days} days)...")
    
    # Fetch documents
    documents = await fetch_documents_from_db(
        days=args.days,
        encounter_id=args.encounter_id,
    )
    
    print(f"Analyzing {len(documents)} documents...")
    
    # Analyze quality
    monitor = TranslationQualityMonitor()
    
    for doc_translations in documents:
        monitor.analyze_document(doc_translations)
    
    # Generate report
    report = monitor.generate_report()
    
    # Output report
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\n✓ Report saved to: {args.output}")
    else:
        print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())
