import React, {useEffect, useRef, useState} from 'react';
import {
	Box,
	Text,
	measureElement,
	useApp,
	useInput,
	type DOMElement,
} from 'ink';
import stringWidth from 'string-width';
import wrapAnsi from 'wrap-ansi';
import Header from './header.js';
import PromptInput from './prompt-input.js';
import Racecar from './racecar.js';
import {splitCommand} from './commands.js';
import {useBackend, type Message} from './use-backend.js';
import {useScreenSize} from './use-screen-size.js';

const questionBackground = '#3a3a3a';
// Messages about how the model is working, hidden by /process-hide.
const processRoles = new Set<Message['role']>(['thinking', 'lookup']);
// Commands handled here without asking the backend.
const localCommands = new Set([
	'quit',
	'process',
	'process-show',
	'process-hide',
]);

function processMode(show: boolean) {
	return show
		? 'Thinking is shown. Thinking and lookups will appear while the model works.'
		: 'Thinking is hidden. A racecar will drive while the model works.';
}

// The question is wrapped and padded by hand so the grey band runs to the
// right edge on every row, not just behind the letters.
function Question({text, width}: {text: string; width: number}) {
	const prefix = '> ';
	const lines = wrapAnsi(text, Math.max(1, width - prefix.length), {
		hard: true,
	}).split('\n');

	return (
		<Box flexDirection="column">
			{lines.map((line, i) => (
				<Text key={i} wrap="truncate" backgroundColor={questionBackground}>
					<Text color="yellow">{i === 0 ? prefix : '  '}</Text>
					{line +
						' '.repeat(Math.max(0, width - prefix.length - stringWidth(line)))}
				</Text>
			))}
		</Box>
	);
}

function Line({message, width}: {message: Message; width: number}) {
	switch (message.role) {
		case 'user':
			return <Question text={message.text} width={width} />;
		case 'thinking':
			return <Text dimColor>{`thinking: ${message.text.trim()}`}</Text>;
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
	const {messages, ready, busy, asking, model, send, request, note} =
		useBackend();
	const {rows, columns} = useScreenSize();
	const viewport = useRef<DOMElement>(null);
	const content = useRef<DOMElement>(null);
	const [viewportHeight, setViewportHeight] = useState(0);
	// Rows of the chat hidden above the screen when showing the newest line.
	const [overflow, setOverflow] = useState(0);
	// How far the user has scrolled up from the newest line.
	const [scroll, setScroll] = useState(0);
	// Whether the model's thinking and lookups are shown while it works.
	const [showProcess, setShowProcess] = useState(true);

	// Measured after every render, since new messages or a resize change it.
	useEffect(() => {
		if (!viewport.current || !content.current) {
			return;
		}

		const visible = measureElement(viewport.current).height;
		const hidden = Math.max(
			0,
			measureElement(content.current).height - visible,
		);
		setViewportHeight(visible);
		setOverflow(hidden);
		setScroll(s => Math.min(s, hidden));
	});

	const scrollBy = (rows: number) => {
		setScroll(s => Math.max(0, Math.min(overflow, s + rows)));
	};

	useInput((_input, key) => {
		if (key.pageUp || key.pageDown) {
			const page = Math.max(1, viewportHeight - 1);
			scrollBy(key.pageUp ? page : -page);
		}
	});

	// Thinking and lookups are kept while hidden, so showing them again brings
	// back the earlier ones too.
	const shown = showProcess
		? messages
		: messages.filter(m => !processRoles.has(m.role));

	let status = 'Ask Gideon... (/ for commands)';
	if (!ready) {
		status = 'Starting backend...';
	} else if (busy) {
		status = 'Thinking...';
	}

	const runCommand = (text: string) => {
		const {name, rest} = splitCommand(text);
		switch (name) {
			case 'process':
				note(processMode(showProcess));
				return;
			case 'process-show':
			case 'process-hide': {
				const show = name === 'process-show';
				setShowProcess(show);
				note(processMode(show));
				return;
			}

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
			case 'processor':
				request({type: 'processor'});
				return;
			default:
				note(`Unknown command: /${name}. Type / to see the list.`);
		}
	};

	return (
		// One row short of the screen: Ink redraws the whole terminal on every
		// change when its output is as tall as the screen.
		<Box flexDirection="column" gap={1} height={rows - 1}>
			{/* Sized by the space left over, never by how much chat it holds. */}
			<Box
				ref={viewport}
				flexDirection="column"
				flexGrow={1}
				flexBasis={0}
				overflow="hidden"
			>
				{/* Starts at the top, then slides up as the chat outgrows the space. */}
				<Box
					ref={content}
					flexDirection="column"
					flexShrink={0}
					gap={1}
					marginTop={-(overflow - scroll)}
				>
					<Header model={model} />
					{shown.map((message, i) => (
						<Line key={i} message={message} width={columns} />
					))}
					{/* Stands in for the hidden thinking until the answer comes. */}
					{asking && !showProcess ? <Racecar width={columns} /> : null}
				</Box>
			</Box>
			<PromptInput
				placeholder={status}
				onSubmit={text => {
					setScroll(0);
					if (text.startsWith('/')) {
						// Commands that do not need the backend work even while it is
						// busy, so thinking can be hidden or shown mid answer.
						const {name} = splitCommand(text);
						if (localCommands.has(name) || (ready && !busy)) {
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
