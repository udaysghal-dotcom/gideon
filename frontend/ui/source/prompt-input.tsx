import React, {useEffect, useState} from 'react';
import {Box, Text, useInput, useStdout} from 'ink';
import {matchCommands, type Command} from './commands.js';
import {isTerminalReport, useMouse} from './use-mouse.js';

type Props = {
	onSubmit: (value: string) => void;
	// Called with how many rows the command menu covers above the input, so the
	// screen can keep at least that many rows for it to draw over.
	onMenuHeight?: (rows: number) => void;
	placeholder?: string;
};

// The input box is three rows: top border, text, bottom border.
const inputHeight = 3;

export default function PromptInput({
	onSubmit,
	onMenuHeight,
	placeholder = 'Ask Gideon...',
}: Props) {
	const {stdout} = useStdout();
	const [value, setValue] = useState('');
	const [cursor, setCursor] = useState(0);
	const [selected, setSelected] = useState(0);

	const matches = matchCommands(value);
	const highlighted = matches[Math.min(selected, matches.length - 1)];
	// One blank row on top separates the menu from the text it covers.
	const menuHeight = matches.length > 0 ? matches.length + 1 : 0;

	useEffect(() => {
		onMenuHeight?.(menuHeight);
	}, [menuHeight, onMenuHeight]);

	const edit = (next: string, nextCursor: number) => {
		setValue(next);
		setCursor(nextCursor);
		setSelected(0);
	};

	const choose = (command: Command) => {
		// A command that needs an argument is filled in so it can be typed.
		if (command.args && value !== `/${command.name}`) {
			const filled = `/${command.name} `;
			edit(filled, filled.length);
			return;
		}

		onSubmit(`/${command.name}`);
		edit('', 0);
	};

	const bottomRow = useMouse(matches.length > 0, event => {
		if (bottomRow === 0) {
			return;
		}

		// The last command sits on the row just above the input box.
		const firstRow = bottomRow - inputHeight - matches.length + 1;
		const command = matches[event.row - firstRow];
		if (!command) {
			return;
		}

		if (event.moved) {
			setSelected(event.row - firstRow);
		} else if (event.pressed && event.button === 0) {
			choose(command);
		}
	});

	useInput((input, key) => {
		if (isTerminalReport(input)) {
			return;
		}

		if (key.return) {
			if (highlighted) {
				choose(highlighted);
				return;
			}

			if (value.trim()) {
				onSubmit(value);
				edit('', 0);
			}

			return;
		}

		if (matches.length > 0 && (key.upArrow || key.downArrow)) {
			const step = key.upArrow ? -1 : 1;
			setSelected(s => (s + step + matches.length) % matches.length);
			return;
		}

		if (key.tab) {
			if (highlighted) {
				const filled = `/${highlighted.name}${highlighted.args ? ' ' : ''}`;
				edit(filled, filled.length);
			}

			return;
		}

		if (key.leftArrow) {
			setCursor(c => Math.max(0, c - 1));
			return;
		}

		if (key.rightArrow) {
			setCursor(c => Math.min(value.length, c + 1));
			return;
		}

		if (key.backspace || key.delete) {
			if (cursor > 0) {
				edit(value.slice(0, cursor - 1) + value.slice(cursor), cursor - 1);
			}

			return;
		}

		if (key.ctrl || key.meta || key.escape) {
			return;
		}

		if (input) {
			edit(
				value.slice(0, cursor) + input + value.slice(cursor),
				cursor + input.length,
			);
		}
	});

	const before = value.slice(0, cursor);
	const atCursor = value[cursor] ?? ' ';
	const after = value.slice(cursor + 1);
	const width = stdout.columns || 80;
	const nameWidth = Math.max(
		...matches.map(c => c.name.length + (c.args ? c.args.length + 1 : 0)),
	);

	return (
		<Box flexDirection="column">
			{matches.length > 0 ? (
				// Drawn after the messages and lifted over them, so it covers them
				// instead of pushing them up. Every row is written out to the full
				// width with spaces, because blank cells would let the text show.
				<Box
					position="absolute"
					flexDirection="column"
					marginTop={-menuHeight}
					width={width}
				>
					<Text>{' '.repeat(width)}</Text>
					{matches.map(command => {
						const isHighlighted = command === highlighted;
						const label = `  /${command.name}${
							command.args ? ` ${command.args}` : ''
						}`.padEnd(nameWidth + 7);
						const description = command.description.padEnd(
							Math.max(0, width - label.length),
						);
						return (
							<Text key={command.name} wrap="truncate">
								<Text color={isHighlighted ? 'yellow' : undefined}>
									{label}
								</Text>
								<Text dimColor={!isHighlighted}>{description}</Text>
							</Text>
						);
					})}
				</Box>
			) : null}
			<Box borderStyle="round" borderColor="gray" paddingX={1}>
				<Text color="yellow">{'> '}</Text>
				{value.length === 0 ? (
					<>
						<Text inverse> </Text>
						<Text dimColor>{placeholder}</Text>
					</>
				) : (
					<Text>
						{before}
						<Text inverse>{atCursor}</Text>
						{after}
					</Text>
				)}
			</Box>
		</Box>
	);
}
