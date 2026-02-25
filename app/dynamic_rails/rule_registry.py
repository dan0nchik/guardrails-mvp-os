"""
Rule Registry — pre-loaded rule templates by domain.

LLM classifier can reference these templates or create custom rules.
"""
from typing import Dict, List, Any

# Pre-defined rule templates organized by domain
RULE_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    'medical': [
        {
            'rule_id': 'med_disclaimer',
            'domain': 'medical',
            'rule_type': 'require_disclaimer',
            'description': 'Добавить дисклеймер: не заменяет консультацию врача',
            'severity': 'high',
            'condition': 'Любые медицинские советы',
            'action': 'Добавить предупреждение о необходимости консультации с врачом',
        },
        {
            'rule_id': 'med_no_diagnosis',
            'domain': 'medical',
            'rule_type': 'warn',
            'description': 'Предупреждать при попытке постановки диагноза',
            'severity': 'high',
            'condition': 'Запрос на диагностику заболевания',
            'action': 'Предупредить, что ИИ не может ставить диагнозы',
        },
        {
            'rule_id': 'med_block_surgery',
            'domain': 'medical',
            'rule_type': 'block',
            'description': 'Блокировать инструкции по хирургическим процедурам',
            'severity': 'critical',
            'condition': 'Запрос инструкций по хирургии или самолечению',
            'action': 'Заблокировать и перенаправить к врачу',
        },
        {
            'rule_id': 'med_no_dosage',
            'domain': 'medical',
            'rule_type': 'block',
            'description': 'Блокировать конкретные дозировки лекарств',
            'severity': 'critical',
            'condition': 'Запрос конкретных дозировок препаратов',
            'action': 'Заблокировать и направить к фармацевту/врачу',
        },
    ],
    'financial': [
        {
            'rule_id': 'fin_disclaimer',
            'domain': 'financial',
            'rule_type': 'require_disclaimer',
            'description': 'Добавить дисклеймер: не является инвестиционным советом',
            'severity': 'high',
            'condition': 'Обсуждение инвестиций или финансовых решений',
            'action': 'Добавить предупреждение о рисках',
        },
        {
            'rule_id': 'fin_no_specific_advice',
            'domain': 'financial',
            'rule_type': 'warn',
            'description': 'Предупреждать при конкретных инвестиционных рекомендациях',
            'severity': 'high',
            'condition': 'Рекомендация купить/продать конкретные активы',
            'action': 'Предупредить о необходимости консультации с финансовым советником',
        },
        {
            'rule_id': 'fin_regulatory',
            'domain': 'financial',
            'rule_type': 'require_disclaimer',
            'description': 'Соответствие регуляторным требованиям',
            'severity': 'medium',
            'condition': 'Обсуждение регулируемых финансовых продуктов',
            'action': 'Упомянуть регуляторные ограничения',
        },
    ],
    'legal': [
        {
            'rule_id': 'legal_disclaimer',
            'domain': 'legal',
            'rule_type': 'require_disclaimer',
            'description': 'Добавить дисклеймер: не является юридической консультацией',
            'severity': 'high',
            'condition': 'Любые юридические вопросы',
            'action': 'Добавить предупреждение о необходимости юриста',
        },
        {
            'rule_id': 'legal_no_representation',
            'domain': 'legal',
            'rule_type': 'block',
            'description': 'Блокировать составление юридических документов',
            'severity': 'high',
            'condition': 'Запрос на составление контрактов, исков, завещаний',
            'action': 'Заблокировать и направить к юристу',
        },
    ],
    'code_security': [
        {
            'rule_id': 'code_no_exploits',
            'domain': 'code_security',
            'rule_type': 'block',
            'description': 'Блокировать создание вредоносного кода',
            'severity': 'critical',
            'condition': 'Запрос на создание эксплойтов, малвари, вирусов',
            'action': 'Заблокировать запрос',
        },
        {
            'rule_id': 'code_review_security',
            'domain': 'code_security',
            'rule_type': 'warn',
            'description': 'Предупреждать о потенциальных уязвимостях в коде',
            'severity': 'medium',
            'condition': 'Генерация кода с потенциальными уязвимостями',
            'action': 'Добавить предупреждение о безопасности',
        },
    ],
    'data_privacy': [
        {
            'rule_id': 'privacy_no_pii',
            'domain': 'data_privacy',
            'rule_type': 'block',
            'description': 'Блокировать запросы на сбор персональных данных',
            'severity': 'critical',
            'condition': 'Запрос на сбор или обработку ПД без согласия',
            'action': 'Заблокировать и объяснить требования GDPR/ФЗ-152',
        },
        {
            'rule_id': 'privacy_gdpr',
            'domain': 'data_privacy',
            'rule_type': 'require_disclaimer',
            'description': 'Требовать упоминание GDPR/ФЗ-152 при обработке данных',
            'severity': 'high',
            'condition': 'Обсуждение обработки персональных данных',
            'action': 'Добавить информацию о применимом законодательстве',
        },
    ],
    'tool_restrictions': [
        {
            'rule_id': 'tool_no_system_cmd',
            'domain': 'tool_restrictions',
            'rule_type': 'block',
            'description': 'Блокировать выполнение системных команд через инструменты',
            'severity': 'critical',
            'condition': 'Попытка выполнения shell-команд или системных операций',
            'action': 'Заблокировать вызов инструмента',
        },
        {
            'rule_id': 'tool_no_external_send',
            'domain': 'tool_restrictions',
            'rule_type': 'block',
            'description': 'Блокировать отправку данных на внешние ресурсы',
            'severity': 'critical',
            'condition': 'Попытка отправки email, HTTP-запросов с конфиденциальными данными',
            'action': 'Заблокировать вызов инструмента',
        },
    ],
}


class RuleRegistry:
    """Registry of pre-loaded rule templates by domain."""

    def __init__(self):
        self.templates = RULE_TEMPLATES.copy()

    def get_templates_for_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get rule templates for a specific domain."""
        return self.templates.get(domain, [])

    def get_all_domains(self) -> List[str]:
        """Get all available domains."""
        return list(self.templates.keys())

    def get_template_by_id(self, rule_id: str) -> Dict[str, Any] | None:
        """Find a template by rule_id across all domains."""
        for domain_rules in self.templates.values():
            for rule in domain_rules:
                if rule['rule_id'] == rule_id:
                    return rule
        return None
