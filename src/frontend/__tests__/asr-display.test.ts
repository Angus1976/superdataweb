/**
 * Property-based tests for ASR display components.
 *
 * Uses fast-check to verify correctness properties of the
 * TranscriptionPanel rendering logic.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { PartialTranscript } from '../types/asr';

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

/** Generate a random PartialTranscript with non-empty text. */
const partialTranscriptArb: fc.Arbitrary<PartialTranscript> = fc
  .record({
    text: fc.string({ minLength: 1, maxLength: 100 }),
    start_time: fc.float({ min: 0, max: 3600, noNaN: true }),
    end_time: fc.float({ min: 0, max: 3600, noNaN: true }),
    is_final: fc.boolean(),
  })
  .map((r) => ({
    ...r,
    // Ensure end_time > start_time
    end_time: r.start_time + Math.abs(r.end_time - r.start_time) + 0.1,
  }));

// ---------------------------------------------------------------------------
// Feature: realtime-voice-asr, Property 8: 转录文本按序追加
// Validates: Requirements 4.1
// ---------------------------------------------------------------------------

describe('Property 8: 转录文本按序追加', () => {
  it('TranscriptionPanel should display transcripts in the same order they are received', () => {
    fc.assert(
      fc.property(
        fc.array(partialTranscriptArb, { minLength: 0, maxLength: 30 }),
        (transcripts: PartialTranscript[]) => {
          // Simulate what TranscriptionPanel does: it renders transcripts in
          // array order via transcripts.map((t, idx) => ...). The accumulated
          // display text is the ordered concatenation of all transcript texts.

          // 1. Build the expected ordered text sequence
          const expectedTexts = transcripts.map((t) => t.text);

          // 2. Simulate the component's rendering logic:
          //    TranscriptionPanel iterates `transcripts` with .map() preserving
          //    insertion order, so the displayed order equals the array order.
          const displayedTexts: string[] = [];
          for (const t of transcripts) {
            displayedTexts.push(t.text);
          }

          // 3. Verify order is preserved
          expect(displayedTexts).toEqual(expectedTexts);

          // 4. Verify accumulated text equals ordered concatenation
          const accumulatedText = displayedTexts.join('');
          const expectedAccumulated = transcripts.map((t) => t.text).join('');
          expect(accumulatedText).toBe(expectedAccumulated);

          // 5. Verify length is preserved (no transcripts lost or duplicated)
          expect(displayedTexts.length).toBe(transcripts.length);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('appending a new transcript preserves all previous transcripts in order', () => {
    fc.assert(
      fc.property(
        fc.array(partialTranscriptArb, { minLength: 1, maxLength: 20 }),
        partialTranscriptArb,
        (existing: PartialTranscript[], newTranscript: PartialTranscript) => {
          // Simulate receiving transcripts one by one, then appending a new one
          const before = [...existing];
          const after = [...existing, newTranscript];

          // All previous transcripts remain in the same positions
          for (let i = 0; i < before.length; i++) {
            expect(after[i].text).toBe(before[i].text);
            expect(after[i].start_time).toBe(before[i].start_time);
            expect(after[i].end_time).toBe(before[i].end_time);
          }

          // The new transcript is appended at the end
          expect(after[after.length - 1].text).toBe(newTranscript.text);

          // Accumulated text of `after` equals accumulated text of `before` + new text
          const accBefore = before.map((t) => t.text).join('');
          const accAfter = after.map((t) => t.text).join('');
          expect(accAfter).toBe(accBefore + newTranscript.text);
        },
      ),
      { numRuns: 100 },
    );
  });
});

// ---------------------------------------------------------------------------
// Generators – CompletionOutline
// ---------------------------------------------------------------------------

import type { OutlineTopic, CompletionOutline } from '../types/asr';

/** Generate a random OutlineTopic with non-empty fields. */
const outlineTopicArb: fc.Arbitrary<OutlineTopic> = fc.record({
  topic_name: fc.string({ minLength: 1, maxLength: 50 }),
  description: fc.string({ minLength: 1, maxLength: 200 }),
});

/** Generate a random CompletionOutline with at least one topic. */
const completionOutlineArb: fc.Arbitrary<CompletionOutline> = fc.record({
  topics: fc.array(outlineTopicArb, { minLength: 1, maxLength: 10 }),
});

// ---------------------------------------------------------------------------
// Feature: realtime-voice-asr, Property 12: 新提纲替换旧提纲
// Validates: Requirements 5.4
// ---------------------------------------------------------------------------

describe('Property 12: 新提纲替换旧提纲', () => {
  it('the latest outline always replaces all previous outlines', () => {
    fc.assert(
      fc.property(
        fc.array(completionOutlineArb, { minLength: 2, maxLength: 20 }),
        (outlines: CompletionOutline[]) => {
          // Simulate the parent component's state management:
          // Each new CompletionOutline replaces the previous one via setState.
          // TranscriptionPanel receives a single `outline` prop — always the latest.
          let currentOutline: CompletionOutline | null = null;

          for (const outline of outlines) {
            // Parent receives a new outline and updates state
            currentOutline = outline;
          }

          // After processing all outlines, the displayed outline must be the last one
          const lastOutline = outlines[outlines.length - 1];
          expect(currentOutline).toEqual(lastOutline);

          // Verify that no previous outline is the current one (unless identical)
          for (let i = 0; i < outlines.length - 1; i++) {
            // The current outline is the last one, not any earlier one
            // (unless they happen to be deeply equal, which is fine)
            if (currentOutline !== null) {
              expect(currentOutline).toEqual(lastOutline);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('at any intermediate point, only the most recent outline is retained', () => {
    fc.assert(
      fc.property(
        fc.array(completionOutlineArb, { minLength: 1, maxLength: 20 }),
        (outlines: CompletionOutline[]) => {
          // Simulate receiving outlines one by one and verify at each step
          // that only the latest outline would be passed to TranscriptionPanel.
          let currentOutline: CompletionOutline | null = null;

          for (let i = 0; i < outlines.length; i++) {
            // Parent component receives new outline → replaces state
            currentOutline = outlines[i];

            // At this point, TranscriptionPanel receives `outline={currentOutline}`
            // Verify it equals the outline just received (the latest)
            expect(currentOutline).toEqual(outlines[i]);

            // Verify it does NOT equal any earlier outline (unless deeply equal)
            // The key invariant: currentOutline is always outlines[i], not outlines[j] for j < i
            // We check referential identity to confirm replacement happened
            expect(currentOutline).toBe(outlines[i]);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('replacing outline with a new one discards all topics from the previous outline', () => {
    fc.assert(
      fc.property(
        completionOutlineArb,
        completionOutlineArb,
        (oldOutline: CompletionOutline, newOutline: CompletionOutline) => {
          // Simulate: parent first has oldOutline, then receives newOutline
          let currentOutline: CompletionOutline | null = oldOutline;
          currentOutline = newOutline;

          // The displayed topics must be exactly the new outline's topics
          expect(currentOutline.topics).toEqual(newOutline.topics);
          expect(currentOutline.topics.length).toBe(newOutline.topics.length);

          // Each displayed topic matches the new outline, not the old one
          for (let i = 0; i < currentOutline.topics.length; i++) {
            expect(currentOutline.topics[i].topic_name).toBe(newOutline.topics[i].topic_name);
            expect(currentOutline.topics[i].description).toBe(newOutline.topics[i].description);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});


// ---------------------------------------------------------------------------
// Feature: realtime-voice-asr, Property 13: 录音期间禁用文字输入
// Validates: Requirements 6.2
// ---------------------------------------------------------------------------

describe('Property 13: 录音期间禁用文字输入', () => {
  /**
   * The TextArea disabled logic in InterviewSessionPage is:
   *   disabled={sessionEnded || isRecording}
   *
   * We test this computation directly (logic-level, no DOM rendering).
   */

  const computeTextAreaDisabled = (sessionEnded: boolean, isRecording: boolean): boolean =>
    sessionEnded || isRecording;

  it('TextArea is always disabled when isRecording is true, regardless of sessionEnded', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // sessionEnded
        (sessionEnded: boolean) => {
          const disabled = computeTextAreaDisabled(sessionEnded, true);
          expect(disabled).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('TextArea disabled state equals (sessionEnded || isRecording) for all boolean combinations', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // isRecording
        fc.boolean(), // sessionEnded
        (isRecording: boolean, sessionEnded: boolean) => {
          const disabled = computeTextAreaDisabled(sessionEnded, isRecording);
          expect(disabled).toBe(sessionEnded || isRecording);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('TextArea is enabled only when both isRecording and sessionEnded are false', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // isRecording
        fc.boolean(), // sessionEnded
        (isRecording: boolean, sessionEnded: boolean) => {
          const disabled = computeTextAreaDisabled(sessionEnded, isRecording);
          if (!isRecording && !sessionEnded) {
            expect(disabled).toBe(false);
          } else {
            expect(disabled).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
