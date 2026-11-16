import { callBookCountLine, outcomeLabel, weekdayLabel } from './callBook';

describe('call book labels', () => {
  test('weekdays are Monday to Friday only', () => {
    expect(weekdayLabel(0)).toBe('Monday');
    expect(weekdayLabel(4)).toBe('Friday');
    expect(weekdayLabel(5)).toBe('');
    expect(weekdayLabel(6)).toBe('');
  });

  test('ask later stays a visible outcome', () => {
    expect(outcomeLabel('ask_later')).toBe('Ask later');
    expect(outcomeLabel('called')).toBe('Called');
    expect(outcomeLabel('no_answer')).toBe('No answer');
  });

  test('the count line covers called, callable, and cannot-call', () => {
    expect(callBookCountLine({
      called: 2,
      callable: 5,
      cannot_call: 1,
    })).toBe('Called 2 of 5. 1 cannot be called.');
    expect(callBookCountLine(null)).toBe('');
  });
});
