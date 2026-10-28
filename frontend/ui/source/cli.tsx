#!/usr/bin/env node
import React from 'react';
import {render} from 'ink';
import meow from 'meow';
import App from './app.js';

meow(
	`
	Usage
	  $ ui

	Options
		--name  Your name

	Examples
	  $ ui --name=Jane
	  Hello, Jane
`,
	{
		importMeta: import.meta,
		flags: {
			name: {
				type: 'string',
			},
		},
	},
);

// Draw on the terminal's alternate screen, like vim does, so Gideon fills the
// window and the shell comes back as it was on exit.
process.stdout.write('\u001B[?1049h\u001B[H');
process.on('exit', () => {
	process.stdout.write('\u001B[?1049l');
});

render(<App />);
