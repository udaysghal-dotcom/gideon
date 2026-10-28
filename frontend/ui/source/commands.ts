export type Command = {
	name: string;
	args?: string;
	description: string;
};

export const commands: Command[] = [
	{name: 'reset', description: 'Clear the conversation'},
	{name: 'model', args: '<name>', description: 'Show or change the model'},
	{name: 'context', description: 'Show how much of the context is used'},
	{name: 'quit', description: 'Exit Gideon'},
];

/**
 * Commands that start with what is typed after the "/".
 * Returns nothing once a space is typed, because then the name is finished.
 */
export function matchCommands(value: string): Command[] {
	if (!value.startsWith('/') || value.includes(' ')) {
		return [];
	}

	const typed = value.slice(1).toLowerCase();
	return commands.filter(command => command.name.startsWith(typed));
}

/** "/model gemma4:12b" becomes {name: 'model', rest: 'gemma4:12b'}. */
export function splitCommand(text: string) {
	const body = text.trim().slice(1);
	const space = body.indexOf(' ');
	if (space === -1) {
		return {name: body.toLowerCase(), rest: ''};
	}

	return {
		name: body.slice(0, space).toLowerCase(),
		rest: body.slice(space + 1).trim(),
	};
}
