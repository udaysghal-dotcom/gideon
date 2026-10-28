import React, {useState} from 'react';
import {Box, Text, useInput} from 'ink';

type Props = {
	onSubmit: (value: string) => void;
	placeholder?: string;
};

export default function PromptInput({
	onSubmit,
	placeholder = 'Ask Gideon...',
}: Props) {
	const [value, setValue] = useState('');
	const [cursor, setCursor] = useState(0);

	useInput((input, key) => {
		if (key.return) {
			if (value.trim()) {
				onSubmit(value);
				setValue('');
				setCursor(0);
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
				setValue(v => v.slice(0, cursor - 1) + v.slice(cursor));
				setCursor(c => c - 1);
			}

			return;
		}

		if (key.ctrl || key.meta || key.escape || key.tab) {
			return;
		}

		if (input) {
			setValue(v => v.slice(0, cursor) + input + v.slice(cursor));
			setCursor(c => c + input.length);
		}
	});

	const before = value.slice(0, cursor);
	const atCursor = value[cursor] ?? ' ';
	const after = value.slice(cursor + 1);

	return (
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
	);
}
