import {useEffect, useRef, useState} from 'react';
import {useStdin, useStdout} from 'ink';

export type MouseEvent = {
	row: number;
	column: number;
	button: number;
	pressed: boolean;
	moved: boolean;
};

// Turn on reporting of every mouse movement (1003) in SGR format (1006).
const enableMouse = '\u001B[?1003h\u001B[?1006h';
const disableMouse = '\u001B[?1003l\u001B[?1006l';
// Asks the terminal where the cursor is. It answers with ESC[row;columnR.
const askCursor = '\u001B[6n';

const mousePattern = /\[<(\d+);(\d+);(\d+)([Mm])/g;
const cursorPattern = /\[(\d+);(\d+)R/;

/** True when the text is a mouse or cursor report rather than typing. */
export function isTerminalReport(input: string) {
	return /\[<\d+;\d+;\d+[Mm]|\[\d+;\d+R/.test(input);
}

/**
 * While enabled, reports mouse events and returns the terminal row of the
 * last line Ink drew (1 is the top row), or 0 before the terminal answers.
 */
export function useMouse(
	enabled: boolean,
	onEvent: (event: MouseEvent) => void,
): number {
	const {stdout} = useStdout();
	const {internal_eventEmitter: events} = useStdin();
	const [bottomRow, setBottomRow] = useState(0);
	const handler = useRef(onEvent);
	handler.current = onEvent;

	useEffect(() => {
		if (!enabled) {
			return;
		}

		const restore = () => stdout.write(disableMouse);
		stdout.write(enableMouse);
		process.once('exit', restore);

		const handleData = (data: unknown) => {
			const text = String(data);

			const cursor = cursorPattern.exec(text);
			if (cursor) {
				const row = Number(cursor[1]);
				// Ink ends its frame with a newline, leaving the cursor in column 1
				// on the row below. A frame taller than the screen has no newline.
				setBottomRow(Number(cursor[2]) === 1 ? row - 1 : row);
			}

			for (const match of text.matchAll(mousePattern)) {
				const code = Number(match[1]);
				handler.current({
					button: code & 3,
					moved: (code & 32) !== 0,
					column: Number(match[2]),
					row: Number(match[3]),
					pressed: match[4] === 'M',
				});
			}
		};

		events.on('input', handleData);
		return () => {
			events.removeListener('input', handleData);
			process.removeListener('exit', restore);
			restore();
			setBottomRow(0);
		};
	}, [enabled, stdout, events]);

	// Ink draws a moment after React commits, so ask for the cursor after that.
	useEffect(() => {
		if (!enabled) {
			return;
		}

		const timer = setTimeout(() => stdout.write(askCursor), 50);
		return () => {
			clearTimeout(timer);
		};
	});

	return bottomRow;
}
