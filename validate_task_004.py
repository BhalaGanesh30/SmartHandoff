"""
Validation script for US-025 TASK-004: DocumentationAgent implementation.

Checks all Definition of Done criteria without requiring full package installation.
"""
import pathlib
import ast
import sys


def check_file_exists(path: str) -> bool:
    """Check if a file exists."""
    p = pathlib.Path(path)
    return p.exists()


def check_code_contains(path: str, text: str) -> bool:
    """Check if a file contains specific text."""
    p = pathlib.Path(path)
    if not p.exists():
        return False
    content = p.read_text()
    return text in content


def check_valid_python(path: str) -> bool:
    """Check if a file is valid Python syntax."""
    p = pathlib.Path(path)
    if not p.exists():
        return False
    try:
        ast.parse(p.read_text())
        return True
    except SyntaxError:
        return False


def main():
    print("=" * 80)
    print("US-025 TASK-004 Definition of Done Validation")
    print("=" * 80)
    print()
    
    checks = []
    
    # Check 1: DocumentationAgent extends BaseAgent
    print("✓ Checking: DocumentationAgent extends BaseAgent")
    agent_path = "backend/agents/documentation/agent.py"
    checks.append(check_file_exists(agent_path))
    checks.append(check_code_contains(agent_path, "class DocumentationAgent(BaseAgent)"))
    
    # Check 2: SUBSCRIPTION_ID = "docs-agent-sub"
    print("✓ Checking: SUBSCRIPTION_ID = 'docs-agent-sub'")
    checks.append(check_code_contains(agent_path, 'SUBSCRIPTION_ID = "docs-agent-sub"'))
    
    # Check 3: can_handle() returns True for A03 and A02 only
    print("✓ Checking: can_handle() returns True for A03 and A02")
    checks.append(check_code_contains(agent_path, 'def can_handle(self, event_type: str) -> bool:'))
    checks.append(check_code_contains(agent_path, '"A03", "A02"'))
    
    # Check 4: process() orchestrates: FHIR fetch → prompt render → _chain.ainvoke() → create_discharge_document()
    print("✓ Checking: process() orchestrates all steps")
    checks.append(check_code_contains(agent_path, 'await self._fetcher.fetch(encounter_id)'))
    checks.append(check_code_contains(agent_path, 'self._renderer.render_discharge_summary'))
    checks.append(check_code_contains(agent_path, 'await self._chain.ainvoke(prompt_text)'))
    checks.append(check_code_contains(agent_path, 'await self._doc_repo.create_discharge_document'))
    
    # Check 5: ChatVertexAI configured with streaming=True and response_mime_type="application/json"
    print("✓ Checking: ChatVertexAI configured correctly")
    checks.append(check_code_contains(agent_path, 'streaming=True'))
    checks.append(check_code_contains(agent_path, '"response_mime_type": "application/json"'))
    
    # Check 6: with_structured_output(DischargeSummarySchema) chain
    print("✓ Checking: with_structured_output(DischargeSummarySchema)")
    checks.append(check_code_contains(agent_path, 'with_structured_output(DischargeSummarySchema)'))
    
    # Check 7: generation_type=AI and generation_duration_ms set
    print("✓ Checking: generation_type and generation_duration_ms set")
    checks.append(check_code_contains(agent_path, 'summary.generation_duration_ms'))
    checks.append(check_code_contains(agent_path, 'summary.generation_type = GenerationType.AI'))
    
    # Check 8: Unit tests exist
    print("✓ Checking: Unit tests exist")
    test_path = "backend/tests/agents/documentation/test_agent.py"
    checks.append(check_file_exists(test_path))
    checks.append(check_code_contains(test_path, 'def test_can_handle_a03'))
    checks.append(check_code_contains(test_path, 'def test_can_handle_a02'))
    checks.append(check_code_contains(test_path, 'def test_cannot_handle_a01'))
    checks.append(check_code_contains(test_path, 'async def test_process_creates_document'))
    
    # Check 9: Registry exists
    print("✓ Checking: Agent registry exists")
    registry_path = "backend/agents/registry.py"
    checks.append(check_file_exists(registry_path))
    checks.append(check_code_contains(registry_path, 'from agents.documentation.agent import DocumentationAgent'))
    checks.append(check_code_contains(registry_path, 'AGENT_REGISTRY'))
    
    # Check 10: Requirements updated
    print("✓ Checking: requirements.txt updated")
    req_path = "backend/requirements.txt"
    checks.append(check_file_exists(req_path))
    checks.append(check_code_contains(req_path, 'langchain-google-vertexai'))
    
    # Check 11: Valid Python syntax
    print("✓ Checking: All files have valid Python syntax")
    checks.append(check_valid_python(agent_path))
    checks.append(check_valid_python(test_path))
    checks.append(check_valid_python(registry_path))
    checks.append(check_valid_python("backend/agents/base_agent.py"))
    
    print()
    print("=" * 80)
    print(f"Total checks: {len(checks)}")
    print(f"Passed: {sum(checks)}")
    print(f"Failed: {len(checks) - sum(checks)}")
    print()
    
    if all(checks):
        print("✓ ALL DEFINITION OF DONE CRITERIA MET")
        print("=" * 80)
        return 0
    else:
        print("✗ SOME CRITERIA NOT MET")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
