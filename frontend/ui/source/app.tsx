import React, {useState} from 'react';
import {Box, Text} from 'ink';
import PromptInput from './prompt-input.js';

export default function App() {
	const [messages, setMessages] = useState<string[]>([]);

	return (
		<Box flexDirection="column">
			{messages.map((message, i) => (
				<Text key={i}>
					<Text color="cyan">{'> '}</Text>
					{message}
				</Text>
			))}
			<PromptInput onSubmit={message => setMessages(m => [...m, message])} />
		</Box>
	);
}
