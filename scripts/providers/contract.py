"""Faker provider for generating realistic contract data."""

import random

from faker.providers import BaseProvider

from providers.style import generate_style

CONTRACT_TEMPLATES = {
    "consulting": {
        "title": "Consulting Services Agreement",
        "type": "Consulting Agreement",
        "party_a_role": "Client",
        "party_b_role": "Consultant",
        "sections": [
            {"title": "Scope of Services", "clauses": [
                "Consultant shall provide the professional consulting services described in Exhibit A attached hereto.",
                "Consultant shall devote sufficient time, attention, and resources to perform the Services in a professional and workmanlike manner.",
                "Any changes to the scope of Services shall require written approval from both parties.",
            ]},
            {"title": "Compensation", "clauses": [
                "Client shall pay Consultant a fee of {rate} per hour for Services rendered.",
                "Consultant shall submit monthly itemized statements detailing hours worked and Services performed.",
                "Payment shall be due within thirty (30) days of receipt of each statement.",
            ]},
            {"title": "Term and Termination", "clauses": [
                "This Agreement shall commence on the Effective Date and continue for a period of {duration}.",
                "Either party may terminate this Agreement upon thirty (30) days prior written notice.",
                "Upon termination, Client shall pay Consultant for all Services performed through the effective date of termination.",
            ]},
            {"title": "Confidentiality", "clauses": [
                "Consultant agrees to maintain in strict confidence all proprietary information disclosed by Client.",
                "This obligation shall survive termination of this Agreement for a period of two (2) years.",
            ]},
            {"title": "Intellectual Property", "clauses": [
                "All work product created by Consultant in the course of performing Services shall be the sole property of Client.",
                "Consultant hereby assigns all rights, title, and interest in such work product to Client.",
            ]},
        ],
    },
    "nda": {
        "title": "Non-Disclosure Agreement",
        "type": "Confidentiality Agreement",
        "party_a_role": "Disclosing Party",
        "party_b_role": "Receiving Party",
        "sections": [
            {"title": "Definition of Confidential Information", "clauses": [
                "Confidential Information means any and all non-public information, whether written, oral, electronic, or visual, disclosed by the Disclosing Party.",
                "Confidential Information includes but is not limited to trade secrets, business plans, financial data, customer lists, technical specifications, and proprietary software.",
                "Confidential Information does not include information that is or becomes publicly available through no fault of the Receiving Party.",
            ]},
            {"title": "Obligations of Receiving Party", "clauses": [
                "The Receiving Party shall use the Confidential Information solely for the purpose of evaluating a potential business relationship.",
                "The Receiving Party shall not disclose the Confidential Information to any third party without prior written consent.",
                "The Receiving Party shall protect the Confidential Information with at least the same degree of care used to protect its own confidential information.",
            ]},
            {"title": "Term", "clauses": [
                "This Agreement shall remain in effect for a period of {duration} from the Effective Date.",
                "The obligations of confidentiality shall survive the expiration or termination of this Agreement for a period of three (3) years.",
            ]},
            {"title": "Return of Materials", "clauses": [
                "Upon written request or termination, the Receiving Party shall promptly return or destroy all Confidential Information and any copies thereof.",
                "The Receiving Party shall certify in writing that all Confidential Information has been returned or destroyed.",
            ]},
        ],
    },
    "employment": {
        "title": "Employment Agreement",
        "type": "Employment Contract",
        "party_a_role": "Employer",
        "party_b_role": "Employee",
        "sections": [
            {"title": "Position and Duties", "clauses": [
                "Employer hereby employs Employee in the position of {job_title}.",
                "Employee shall perform such duties as are customarily associated with the position and as may be assigned from time to time by Employer.",
                "Employee shall devote full-time professional efforts to the performance of duties hereunder.",
            ]},
            {"title": "Compensation and Benefits", "clauses": [
                "Employer shall pay Employee an annual base salary of {salary}, payable in accordance with Employer's standard payroll practices.",
                "Employee shall be eligible to participate in all employee benefit plans and programs generally available to employees of similar status.",
                "Employee shall be entitled to {pto_days} days of paid time off per calendar year.",
            ]},
            {"title": "Term and Termination", "clauses": [
                "Employment under this Agreement shall commence on the Effective Date and shall continue on an at-will basis.",
                "Either party may terminate this Agreement at any time with or without cause upon {notice_period} days written notice.",
                "Upon termination, Employee shall return all company property, documents, and materials.",
            ]},
            {"title": "Non-Compete", "clauses": [
                "During employment and for a period of {noncompete_months} months thereafter, Employee shall not directly or indirectly engage in any business that competes with Employer.",
                "This restriction shall apply within a {noncompete_radius} mile radius of Employer's principal place of business.",
            ]},
        ],
    },
    "service": {
        "title": "Master Service Agreement",
        "type": "Service Agreement",
        "party_a_role": "Client",
        "party_b_role": "Service Provider",
        "sections": [
            {"title": "Services", "clauses": [
                "Service Provider shall provide the services described in one or more Statements of Work executed by the parties.",
                "Each Statement of Work shall describe the specific services, deliverables, timeline, and fees applicable thereto.",
                "Service Provider shall perform all Services in a professional manner consistent with industry standards.",
            ]},
            {"title": "Fees and Payment", "clauses": [
                "Client shall pay Service Provider the fees set forth in the applicable Statement of Work.",
                "Service Provider shall submit monthly statements for Services rendered. Payment shall be due within {payment_days} days.",
                "Late payments shall accrue interest at the rate of 1.5% per month or the maximum rate permitted by law.",
            ]},
            {"title": "Term", "clauses": [
                "This Agreement shall commence on the Effective Date and continue for an initial term of {duration}.",
                "This Agreement shall automatically renew for successive one-year periods unless either party provides written notice of non-renewal at least sixty (60) days prior to expiration.",
            ]},
            {"title": "Limitation of Liability", "clauses": [
                "In no event shall either party be liable for any indirect, incidental, special, or consequential damages.",
                "The total aggregate liability of Service Provider under this Agreement shall not exceed the total fees paid by Client during the twelve (12) months preceding the claim.",
            ]},
            {"title": "Indemnification", "clauses": [
                "Each party shall indemnify, defend, and hold harmless the other party from any third-party claims arising from its breach of this Agreement.",
                "The indemnifying party shall have sole control of the defense and settlement of any such claim.",
            ]},
        ],
    },
}

ENTITY_TYPES = ["Delaware corporation", "New York LLC", "California corporation", "Texas limited partnership", "Florida LLC", "Nevada corporation", "Wyoming LLC"]

TITLES = {
    "executive": ["CEO", "President", "Managing Director", "VP of Operations", "General Counsel", "CFO", "COO"],
    "other": ["Owner", "Principal", "Director", "Partner", "Manager", "Founder"],
}

CONTRACT_FONTS = ["Georgia, serif", "Times New Roman, serif", "Garamond, serif", "Arial, sans-serif"]

RECITAL_SETS = [
    [
        "{company_a} desires to engage the services of {company_b} for professional consulting",
        "The parties wish to set forth the terms and conditions governing such engagement",
    ],
    [
        "The parties have been engaged in discussions regarding a potential business relationship",
        "In connection therewith, the parties may disclose certain confidential and proprietary information",
    ],
    [
        "{company_a} is in the business of providing {industry} services",
        "{company_b} desires to retain the services of {company_a} on the terms set forth herein",
    ],
]

EXHIBIT_SETS = [
    ["Exhibit A - Statement of Work", "Exhibit B - Fee Schedule"],
    ["Exhibit A - Scope of Services", "Exhibit B - Payment Schedule", "Exhibit C - Insurance Requirements"],
    ["Schedule A - Compensation Details"],
    ["Exhibit A - Technical Specifications", "Exhibit B - Acceptance Criteria"],
    None,
    None,
]


class ContractProvider(BaseProvider):
    """Generate complete contract data dicts ready for Jinja2 templates."""

    def contract_type(self) -> str:
        return self.random_element(list(CONTRACT_TEMPLATES.keys()))

    def _fill_placeholders(self, clause: str) -> str:
        """Replace {rate}, {duration}, etc. with random values."""
        replacements = {
            "{rate}": f"${self.random_int(min=100, max=500)}",
            "{duration}": self.random_element(["six (6) months", "one (1) year", "twelve (12) months", "two (2) years"]),
            "{salary}": f"${self.random_int(min=60, max=250) * 1000:,}",
            "{job_title}": self.generator.job(),
            "{pto_days}": str(self.random_int(min=10, max=25)),
            "{notice_period}": str(self.random_element([14, 30, 60, 90])),
            "{noncompete_months}": str(self.random_element([6, 12, 18, 24])),
            "{noncompete_radius}": str(self.random_element([25, 50, 100])),
            "{payment_days}": str(self.random_element([15, 30, 45])),
        }
        for placeholder, value in replacements.items():
            clause = clause.replace(placeholder, value)
        return clause

    def contract_sections(self, contract_type: str) -> list[dict]:
        """Build numbered sections with filled-in clauses."""
        template = CONTRACT_TEMPLATES[contract_type]
        sections = []
        for i, section in enumerate(template["sections"], 1):
            clauses = [self._fill_placeholders(c) for c in section["clauses"]]
            sections.append({"number": i, "title": section["title"], "clauses": clauses})
        return sections

    def contract_data(self, contract_type: str | None = None) -> dict:
        """Complete contract dict matching the Jinja2 template variables."""
        if contract_type is None:
            contract_type = self.contract_type()

        template = CONTRACT_TEMPLATES[contract_type]
        sections = self.contract_sections(contract_type)

        party_a = self.generator.company()
        party_b = self.generator.company() if contract_type != "employment" else self.generator.name()
        industry = self.random_element(["technology", "consulting", "manufacturing", "marketing", "logistics"])

        # fill in recitals with actual party names
        recital_set = self.random_element(RECITAL_SETS + [None])
        recitals = None
        if recital_set:
            recitals = [
                r.replace("{company_a}", party_a).replace("{company_b}", party_b).replace("{industry}", industry)
                for r in recital_set
            ]

        return {
            "font": self.random_element(CONTRACT_FONTS),
            "contract_title": template["title"],
            "contract_type": template["type"],
            "effective_date": self.generator.date_between(start_date="-60d", end_date="+60d").strftime(
                self.random_element(["%B %d, %Y", "%m/%d/%Y", "%d %B %Y"])
            ),
            "party_a_name": party_a,
            "party_a_entity_type": self.random_element(ENTITY_TYPES),
            "party_a_address": self.generator.street_address(),
            "party_a_city": self.generator.city(),
            "party_a_state": self.generator.state_abbr(),
            "party_a_zip": self.generator.postcode(),
            "party_a_role": template["party_a_role"],
            "party_a_signatory": self.generator.name(),
            "party_a_title": self.random_element(TITLES["executive"]),
            "party_b_name": party_b,
            "party_b_entity_type": self.random_element(ENTITY_TYPES + [None]) if contract_type != "employment" else None,
            "party_b_address": self.generator.street_address(),
            "party_b_city": self.generator.city(),
            "party_b_state": self.generator.state_abbr(),
            "party_b_zip": self.generator.postcode(),
            "party_b_role": template["party_b_role"],
            "party_b_signatory": self.generator.name(),
            "party_b_title": self.random_element(TITLES["other"]) if contract_type != "employment" else None,
            "recitals": recitals,
            "sections": sections,
            "exhibits": self.random_element(EXHIBIT_SETS),
            "page_count": self.random_int(min=2, max=8),
            **generate_style(),
        }
