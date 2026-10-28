import React from 'react';
import {Box, Text} from 'ink';
import PromptInput from './prompt-input.js';
import {useBackend, type Message} from './use-backend.js';

function Line({message}: {message: Message}) {
	switch (message.role) {
		case 'user':
			return (
				<Text>
					<Text color="yellow">{'> '}</Text>
					{message.text}
				</Text>
			);
		case 'lookup':
			return <Text dimColor>{message.text}</Text>;
		case 'error':
			return <Text color="red">{message.text}</Text>;
		default:
			return <Text>{message.text}</Text>;
	}
}

export default function App() {
	const {messages, ready, busy, model, send} = useBackend();

	let status = 'Ask Gideon...';
	if (!ready) {
		status = 'Starting backend...';
	} else if (busy) {
		status = 'Thinking...';
	}

	return (
		<Box flexDirection="column" gap={1}>
			{model ? <Text dimColor>Model {model}</Text> : null}
			{messages.map((message, i) => (
				<Line key={i} message={message} />
			))}
			<PromptInput
				placeholder={status}
				onSubmit={text => {
					if (ready && !busy) {
						send(text);
					}
				}}
			/>
		</Box>
	);
}
