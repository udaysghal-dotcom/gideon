import os from 'node:os';
import React from 'react';
import {Box, Text} from 'ink';

const version = 'v0.01';

// Each letter is two rows of half blocks. The UNSW letters are yellow.
const sunswift = [
	{rows: ['█▀', '▄█'], yellow: false},
	{rows: ['█ █', '█▄█'], yellow: true},
	{rows: ['█▄ █', '█ ▀█'], yellow: true},
	{rows: ['█▀', '▄█'], yellow: true},
	{rows: ['█ █ █', '▀▄▀▄▀'], yellow: true},
	{rows: ['█', '█'], yellow: false},
	{rows: ['█▀', '█▀'], yellow: false},
	{rows: ['▀█▀', ' █ '], yellow: false},
];

// Spaced out so it is as wide as SUNSWIFT.
const racing = [
	'█▀█  ▄▀█  █▀▀   █   █▄ █  █▀▀',
	'█▀▄  █▀█  █▄▄   █   █ ▀█  █▄█',
];

const white = '#ffffff';
// Bright on the top row, darker on the bottom, as in the full size logo.
const yellows = ['#ffe600', '#b38600'];
const grey = '#a0a0a0';

function currentDirectory() {
	const cwd = process.cwd();
	const home = os.homedir();
	return cwd.startsWith(home) ? '~' + cwd.slice(home.length) : cwd;
}

export default function Header({model}: {model: string}) {
	return (
		<Box>
			<Box flexDirection="column" justifyContent="space-between">
				<Box flexDirection="column">
					{[0, 1].map(row => (
						<Text key={row}>
							{sunswift.map((letter, i) => (
								<Text key={i} color={letter.yellow ? yellows[row] : white}>
									{(i > 0 ? ' ' : '') + letter.rows[row]}
								</Text>
							))}
						</Text>
					))}
				</Box>
				<Box flexDirection="column" marginTop={1}>
					{racing.map((row, i) => (
						<Text key={i} color={white}>
							{row}
						</Text>
					))}
				</Box>
			</Box>
			<Box flexDirection="column" justifyContent="space-between" marginLeft={3}>
				<Text>
					<Text bold color={white}>
						Gideon
					</Text>
					<Text color={grey}> {version}</Text>
				</Text>
				<Text color={grey}>{model || 'Starting backend...'}</Text>
				<Text color={grey}>{currentDirectory()}</Text>
			</Box>
		</Box>
	);
}
