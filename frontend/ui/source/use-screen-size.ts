import {useEffect, useState} from 'react';
import {useStdout} from 'ink';

const clearScreen = '\u001B[2J\u001B[H';

// The size the screen was last cleared for. Shared because several components
// use this hook, and a second clear after Ink has redrawn would leave the
// screen blank, since Ink only redraws what changed.
let clearedFor = '';

/** The terminal's size in rows and columns, updated when it is resized. */
export function useScreenSize() {
	const {stdout} = useStdout();
	const read = () => ({rows: stdout.rows || 24, columns: stdout.columns || 80});
	const [size, setSize] = useState(read);

	useEffect(() => {
		const handleResize = () => {
			const next = read();
			const key = `${next.rows}x${next.columns}`;
			if (key !== clearedFor) {
				// The old frame is drawn for the old size, so wipe it and let Ink
				// draw again from the top. This runs before Ink's own handler.
				clearedFor = key;
				stdout.write(clearScreen);
			}

			setSize(next);
		};

		stdout.prependListener('resize', handleResize);
		return () => {
			stdout.removeListener('resize', handleResize);
		};
	}, [stdout]);

	return size;
}
