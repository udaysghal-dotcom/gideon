import {useEffect, useRef} from 'react';
import {useStdin, useStdout} from 'ink';

export type MouseEvent = {
	row: number;
	column: number;
	button: number;
	pressed: boolean;
	moved: boolean;
	// Set when the event is a turn of the scroll wheel.
	wheel?: 'up' | 'down';
};

// Turn on reporting of every mouse movement (1003) in SGR format (1006).
const enableMouse = '\u001B[?1003h\u001B[?1006h';
const disableMouse = '\u001B[?1003l\u001B[?1006l';

const mousePattern = /\[<(\d+);(\d+);(\d+)([Mm])/g;

/** True when the text is a mouse report rather than typing. */
export function isTerminalReport(input: string) {
	return /\[<\d+;\d+;\d+[Mm]/.test(input);
}

/**
 * While enabled, reports mouse events. Rows and columns start at 1 in the top
 * left. The terminal stops selecting text while this is on, so keep it on only
 * while there is something to click.
 */
export function useMouse(
	enabled: boolean,
	onEvent: (event: MouseEvent) => void,
) {
	const {stdout} = useStdout();
	const {internal_eventEmitter: events} = useStdin();
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
			for (const match of String(data).matchAll(mousePattern)) {
				const code = Number(match[1]);
				const isWheel = (code & 64) !== 0;
				handler.current({
					button: code & 3,
					moved: (code & 32) !== 0,
					wheel: isWheel ? (code & 1 ? 'down' : 'up') : undefined,
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
		};
	}, [enabled, stdout, events]);
}
