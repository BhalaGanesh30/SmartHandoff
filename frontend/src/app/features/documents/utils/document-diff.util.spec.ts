/**
 * Unit tests for computeClientDiff utility (US-028 Scenario 2).
 */
import { computeClientDiff } from './document-diff.util';

describe('computeClientDiff', () => {
  it('returns empty object when baseline equals edited', () => {
    const baseline = { medications: 'Aspirin', diet: 'Normal' };
    const result = computeClientDiff(baseline, { ...baseline });
    expect(result).toEqual({});
  });

  it('returns diff entry for changed field', () => {
    const baseline = { medications: 'Aspirin' };
    const edited = { medications: 'Warfarin' };
    const result = computeClientDiff(baseline, edited);
    expect(result).toEqual({
      medications: { old_value: 'Aspirin', new_value: 'Warfarin' },
    });
  });

  it('returns entry with null old_value for newly added field', () => {
    const result = computeClientDiff({}, { follow_up: 'Call Dr Smith' });
    expect(result['follow_up'].old_value).toBeNull();
    expect(result['follow_up'].new_value).toBe('Call Dr Smith');
  });

  it('returns entry with null new_value for removed field', () => {
    const result = computeClientDiff({ diet: 'Low sodium' }, {});
    expect(result['diet'].old_value).toBe('Low sodium');
    expect(result['diet'].new_value).toBeNull();
  });

  it('handles multiple changed fields independently', () => {
    const baseline = { a: '1', b: '2', c: '3' };
    const edited = { a: 'changed', b: '2', c: 'changed' };
    const result = computeClientDiff(baseline, edited);
    expect(Object.keys(result)).toHaveLength(2);
    expect(result['a']).toBeDefined();
    expect(result['c']).toBeDefined();
    expect(result['b']).toBeUndefined();
  });
});
