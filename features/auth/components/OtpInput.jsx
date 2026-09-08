import { useEffect, useRef, useState } from 'react';

/**
 * Four boxes rather than one field.
 *
 * Not decoration: it tells you how many digits are expected before you start
 * typing, and it makes a mistyped digit obvious at a glance. On a phone the
 * `one-time-code` autocomplete lets the keyboard offer the SMS directly, which
 * is the difference between tapping once and switching apps to read a message.
 *
 * **The digits live here, in one array, updated functionally.** The first
 * version derived each box from the incoming `value` prop and wrote the whole
 * string back on every keystroke. That loses characters the moment typing
 * outruns a render: each handler rebuilds from the `value` it captured, so
 * four fast keystrokes all edit the same stale string and only the last
 * survives. Typing "9555" left "9". Functional updates compose instead of
 * racing, which is the difference between working for a careful tester and
 * working for somebody in a hurry.
 *
 * Paste is handled explicitly because people paste the whole code, and a
 * per-box input would otherwise take only the first character.
 */
export default function OtpInput({ value, onChange, length = 4, disabled }) {
  const refs = useRef([]);
  const [digits, setDigits] = useState(() =>
    Array.from({ length }, (_, i) => value[i] ?? ''),
  );

  useEffect(() => {
    refs.current[0]?.focus();
  }, []);

  // Let the parent clear the field, without fighting it on every keystroke.
  useEffect(() => {
    if (value === '') {
      setDigits(Array.from({ length }, () => ''));
    }
  }, [value, length]);

  const commit = (next) => {
    setDigits(next);
    onChange(next.join(''));
  };

  const handleChange = (index, raw) => {
    const digit = raw.replace(/\D/g, '').slice(-1);

    setDigits((prev) => {
      const next = [...prev];
      next[index] = digit;
      onChange(next.join(''));
      return next;
    });

    if (digit && index < length - 1) {
      refs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index, event) => {
    // Backspace on an empty box steps back, which is what every OTP field
    // does and what fingers expect.
    if (event.key === 'Backspace' && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (event) => {
    const pasted = event.clipboardData.getData('text').replace(/\D/g, '');
    if (!pasted) return;

    event.preventDefault();
    const next = Array.from({ length }, (_, i) => pasted[i] ?? '');
    commit(next);
    refs.current[Math.min(pasted.length, length - 1)]?.focus();
  };

  return (
    <div className="otp-input" onPaste={handlePaste}>
      {digits.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          value={digit}
          onChange={(e) => handleChange(index, e.target.value)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          inputMode="numeric"
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          disabled={disabled}
          aria-label={`Digit ${index + 1} of ${length}`}
        />
      ))}
    </div>
  );
}
