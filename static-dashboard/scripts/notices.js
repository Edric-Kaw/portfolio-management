import {readFile,writeFile} from 'node:fs/promises';
const notices=[];for(const [name,version] of [['xlsx','0.20.3'],['plotly.js-dist-min','4.1.2']])notices.push(`${name} ${version}\n${await readFile(`node_modules/${name}/LICENSE`,'utf8')}`);
await writeFile('dist/THIRD_PARTY_NOTICES.txt',notices.join('\n\n----------------------------------------\n\n'));
