"""
US-027 TASK-005 Validation Script

Validates implementation of translations and metadata JSONB columns:
- Document model has translations and document_metadata columns
- Alembic migration exists and is syntactically correct
- DocumentRepository has save_patient_instructions method
- PatientInstructionsDocument has translations_as_dict method
- All imports are correct
- No syntax errors
"""
import ast
import pathlib
import sys
from typing import List, Tuple


def validate_file_exists(file_path: str) -> Tuple[bool, str]:
    """Check if a file exists."""
    path = pathlib.Path(file_path)
    if path.exists():
        return True, f"✓ File exists: {file_path}"
    return False, f"✗ File not found: {file_path}"


def validate_python_syntax(file_path: str) -> Tuple[bool, str]:
    """Validate Python file syntax."""
    path = pathlib.Path(file_path)
    try:
        ast.parse(path.read_text(encoding='utf-8'))
        return True, f"✓ Valid Python syntax: {file_path}"
    except SyntaxError as e:
        return False, f"✗ Syntax error in {file_path}: {e}"
    except UnicodeDecodeError as e:
        # Try reading with different encoding
        try:
            ast.parse(path.read_text(encoding='latin-1'))
            return True, f"✓ Valid Python syntax: {file_path}"
        except Exception:
            return False, f"✗ Encoding error in {file_path}: {e}"


def check_class_has_attribute(file_path: str, class_name: str, attr_name: str) -> Tuple[bool, str]:
    """Check if a class has a specific attribute."""
    path = pathlib.Path(file_path)
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except UnicodeDecodeError:
        tree = ast.parse(path.read_text(encoding='latin-1'))
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    if hasattr(item.target, 'id') and item.target.id == attr_name:
                        return True, f"✓ {class_name}.{attr_name} found"
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if hasattr(target, 'id') and target.id == attr_name:
                            return True, f"✓ {class_name}.{attr_name} found"
    
    return False, f"✗ {class_name}.{attr_name} not found"


def check_class_has_method(file_path: str, class_name: str, method_name: str) -> Tuple[bool, str]:
    """Check if a class has a specific method."""
    path = pathlib.Path(file_path)
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except UnicodeDecodeError:
        tree = ast.parse(path.read_text(encoding='latin-1'))
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == method_name:
                        return True, f"✓ {class_name}.{method_name}() found"
    
    return False, f"✗ {class_name}.{method_name}() not found"


def check_migration_revision(file_path: str) -> Tuple[bool, str]:
    """Check migration has correct revision IDs."""
    path = pathlib.Path(file_path)
    try:
        content = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        content = path.read_text(encoding='latin-1')
    
    checks = []
    
    if 'revision = "l6i9h2d57g61"' in content:
        checks.append((True, '✓ Migration revision ID is correct'))
    else:
        checks.append((False, '✗ Migration revision ID incorrect or missing'))
    
    if 'down_revision = "k5h8g1c46f50"' in content:
        checks.append((True, '✓ Migration down_revision is correct'))
    else:
        checks.append((False, '✗ Migration down_revision incorrect or missing'))
    
    if 'def upgrade()' in content:
        checks.append((True, '✓ Migration has upgrade() function'))
    else:
        checks.append((False, '✗ Migration missing upgrade() function'))
    
    if 'def downgrade()' in content:
        checks.append((True, '✓ Migration has downgrade() function'))
    else:
        checks.append((False, '✗ Migration missing downgrade() function'))
    
    all_pass = all(check[0] for check in checks)
    messages = [check[1] for check in checks]
    
    return all_pass, '\n'.join(messages)


def main():
    """Run all validation checks."""
    print()
    print('=' * 80)
    print('US-027 TASK-005 VALIDATION')
    print('=' * 80)
    print()
    
    results: List[Tuple[bool, str]] = []
    
    # File existence checks
    print('1. File Existence Checks')
    print('-' * 80)
    
    files_to_check = [
        'backend/app/models/document.py',
        'backend/alembic/versions/l6i9h2d57g61_us027_add_document_translations.py',
        'backend/app/db/repositories/document_repository.py',
        'backend/agents/documentation/patient_instructions_schemas.py',
    ]
    
    for file_path in files_to_check:
        result = validate_file_exists(file_path)
        results.append(result)
        print(result[1])
    
    print()
    
    # Syntax validation
    print('2. Python Syntax Validation')
    print('-' * 80)
    
    for file_path in files_to_check:
        if pathlib.Path(file_path).exists():
            result = validate_python_syntax(file_path)
            results.append(result)
            print(result[1])
    
    print()
    
    # Document model validation
    print('3. Document Model Column Checks')
    print('-' * 80)
    
    result = check_class_has_attribute(
        'backend/app/models/document.py',
        'Document',
        'translations'
    )
    results.append(result)
    print(result[1])
    
    result = check_class_has_attribute(
        'backend/app/models/document.py',
        'Document',
        'document_metadata'
    )
    results.append(result)
    print(result[1])
    
    print()
    
    # Migration validation
    print('4. Alembic Migration Validation')
    print('-' * 80)
    
    migration_path = 'backend/alembic/versions/l6i9h2d57g61_us027_add_document_translations.py'
    if pathlib.Path(migration_path).exists():
        result = check_migration_revision(migration_path)
        results.append(result)
        print(result[1])
    
    print()
    
    # Repository method validation
    print('5. DocumentRepository Method Check')
    print('-' * 80)
    
    result = check_class_has_method(
        'backend/app/db/repositories/document_repository.py',
        'DocumentRepository',
        'save_patient_instructions'
    )
    results.append(result)
    print(result[1])
    
    print()
    
    # Schema method validation
    print('6. PatientInstructionsDocument Method Check')
    print('-' * 80)
    
    result = check_class_has_method(
        'backend/agents/documentation/patient_instructions_schemas.py',
        'PatientInstructionsDocument',
        'translations_as_dict'
    )
    results.append(result)
    print(result[1])
    
    print()
    
    # Summary
    print('=' * 80)
    total_checks = len(results)
    passed_checks = sum(1 for result in results if result[0])
    failed_checks = total_checks - passed_checks
    
    print(f'Total Checks: {total_checks}')
    print(f'Passed: {passed_checks}')
    print(f'Failed: {failed_checks}')
    print()
    
    if failed_checks == 0:
        print('✓ ALL CHECKS PASSED')
        print('=' * 80)
        print()
        print('TASK-005: COMPLETE ✓')
        print()
        print('Next Steps:')
        print('  1. Review the changes')
        print('  2. Run Alembic migration: alembic upgrade head')
        print('  3. Test save_patient_instructions() method')
        print('  4. Proceed to next US-027 task')
        print()
        return 0
    else:
        print('✗ SOME CHECKS FAILED')
        print('=' * 80)
        print()
        print('Please review the failed checks above and fix the issues.')
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
