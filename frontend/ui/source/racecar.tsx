import React, {useEffect, useState} from 'react';
import {Box, Text} from 'ink';

// Same car as backend/chatbot/racecar.py, which the old terminal chat used.
const car = ["  _.-''''-._", " '-(o)---(o)-'"];
const road = '_';
const spacesPerSecond = 3;

/** Car rows and the road for one step, wrapping past the right edge. */
function frame(position: number, width: number) {
	const rows = car.map(text => {
		const cells = Array.from({length: width}, () => ' ');
		for (const [offset, char] of [...text].entries()) {
			if (char !== ' ') {
				cells[(position + offset) % width] = char;
			}
		}

		return cells.join('');
	});
	rows.push(road.repeat(width));
	return rows;
}

/** A car that drives along a road while the model works. */
export default function Racecar({width}: {width: number}) {
	const [position, setPosition] = useState(0);

	useEffect(() => {
		const timer = setInterval(() => {
			setPosition(p => p + 1);
		}, 1000 / spacesPerSecond);
		return () => {
			clearInterval(timer);
		};
	}, []);

	const roadWidth = Math.max(width, ...car.map(text => text.length));
	return (
		<Box flexDirection="column">
			{frame(position % roadWidth, roadWidth).map((row, i) => (
				<Text key={i} wrap="truncate">
					{row}
				</Text>
			))}
		</Box>
	);
}
