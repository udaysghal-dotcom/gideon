import {spawn, type ChildProcess} from 'node:child_process';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {useCallback, useEffect, useRef, useState} from 'react';

export type Message = {
	role: 'user' | 'assistant' | 'thinking' | 'lookup' | 'info' | 'error';
	text: string;
};

type BackendEvent =
	| {type: 'ready'; model: string; num_ctx: number}
	| {type: 'thinking'; text: string}
	| {type: 'lookup'; text: string}
	| {type: 'answer'; text: string}
	| {type: 'info'; text: string}
	| {type: 'model'; model: string}
	| {type: 'error'; text: string}
	| {type: 'done'};

export type BackendRequest =
	| {type: 'reset'}
	| {type: 'model'; name: string}
	| {type: 'context'}
	| {type: 'processor'};

const here = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(here, '../../../backend');
const python = path.join(backendDir, '.venv/bin/python');

export function useBackend() {
	const [messages, setMessages] = useState<Message[]>([]);
	const [ready, setReady] = useState(false);
	const [busy, setBusy] = useState(false);
	// Busy answering a question, rather than with a command like /reset.
	const [asking, setAsking] = useState(false);
	const [model, setModel] = useState('');
	const child = useRef<ChildProcess>();

	useEffect(() => {
		const proc = spawn(python, ['-m', 'chatbot.bridge'], {
			cwd: backendDir,
			stdio: ['pipe', 'pipe', 'pipe'],
		});
		child.current = proc;

		const add = (message: Message) => {
			setMessages(m => [...m, message]);
		};

		let stderr = '';
		proc.stderr!.on('data', (chunk: Buffer) => {
			stderr = (stderr + chunk.toString()).slice(-2000);
		});

		proc.on('error', error => {
			add({
				role: 'error',
				text: `Could not start the backend: ${error.message}`,
			});
		});

		proc.on('exit', code => {
			setReady(false);
			setBusy(false);
			setAsking(false);
			if (code) {
				add({
					role: 'error',
					text: `Backend exited (code ${code}).\n${stderr.trim()}`,
				});
			}
		});

		createInterface({input: proc.stdout!}).on('line', line => {
			let event: BackendEvent;
			try {
				event = JSON.parse(line) as BackendEvent;
			} catch {
				return;
			}

			switch (event.type) {
				case 'ready':
					setModel(event.model);
					setReady(true);
					break;
				case 'thinking':
					// Thinking streams in small pieces, so they are joined into one
					// message until something else is said.
					setMessages(m => {
						const last = m[m.length - 1];
						if (last?.role !== 'thinking') {
							return [...m, {role: 'thinking', text: event.text}];
						}

						return [...m.slice(0, -1), {...last, text: last.text + event.text}];
					});
					break;
				case 'lookup':
					add({role: 'lookup', text: event.text});
					break;
				case 'answer':
					add({role: 'assistant', text: event.text});
					break;
				case 'info':
					add({role: 'info', text: event.text});
					break;
				case 'model':
					setModel(event.model);
					break;
				case 'error':
					add({role: 'error', text: event.text});
					break;
				case 'done':
					setBusy(false);
					setAsking(false);
					break;
				default:
					break;
			}
		});

		return () => {
			proc.kill();
		};
	}, []);

	const write = useCallback((payload: object) => {
		const proc = child.current;
		if (!proc?.stdin?.writable) {
			return false;
		}

		setBusy(true);
		proc.stdin.write(JSON.stringify(payload) + '\n');
		return true;
	}, []);

	const send = useCallback(
		(text: string) => {
			if (write({type: 'ask', text})) {
				setAsking(true);
				setMessages(m => [...m, {role: 'user', text}]);
			}
		},
		[write],
	);

	const request = useCallback(
		(payload: BackendRequest) => {
			write(payload);
		},
		[write],
	);

	const note = useCallback((text: string) => {
		setMessages(m => [...m, {role: 'info', text}]);
	}, []);

	return {messages, ready, busy, asking, model, send, request, note};
}
