import React, {useState} from 'react';
import {Box, Text, useApp} from 'ink';
import Header from './header.js';
import PromptInput from './prompt-input.js';
import {splitCommand} from './commands.js';
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
		case 'info':
			return <Text dimColor>{message.text}</Text>;
		case 'error':
			return <Text color="red">{message.text}</Text>;
		default:
			return <Text>{message.text}</Text>;
	}
}

export default function App() {
	const {exit} = useApp();
	const {messages, ready, busy, model, send, request, note} = useBackend();
	const [menuHeight, setMenuHeight] = useState(0);

	let status = 'Ask Gideon... (/ for commands)';
	if (!ready) {
		status = 'Starting backend...';
	} else if (busy) {
		status = 'Thinking...';
	}

	const runCommand = (text: string) => {
		const {name, rest} = splitCommand(text);
		switch (name) {
			case 'quit':
				exit();
				return;
			case 'reset':
				request({type: 'reset'});
				return;
			case 'model':
				request({type: 'model', name: rest});
				return;
			case 'context':
				request({type: 'context'});
				return;
			default:
				note(`Unknown command: /${name}. Type / to see the list.`);
		}
	};

	return (
		<Box flexDirection="column" gap={1}>
			{/* Keeps enough rows above the input for the command menu to cover. */}
			<Box flexDirection="column" gap={1} minHeight={menuHeight}>
				<Header model={model} />
				{messages.map((message, i) => (
					<Line key={i} message={message} />
				))}
			</Box>
			<PromptInput
				placeholder={status}
				onMenuHeight={setMenuHeight}
				onSubmit={text => {
					if (text.startsWith('/')) {
						// Quit works even while the backend is busy.
						const {name} = splitCommand(text);
						if (name === 'quit' || (ready && !busy)) {
							runCommand(text);
						}

						return;
					}

					if (ready && !busy) {
						send(text);
					}
				}}
			/>
		</Box>
	);
}
