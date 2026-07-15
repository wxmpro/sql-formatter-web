/**
 * Pyodide 加载器：把 formatter_core 加载到浏览器内的 Python 运行时。
 */

const FORMATTER_CORE_FILES = [
    '__init__.py',
    'main.py',
    'lexer.py',
    'constants.py',
    'fsm_core.py',
    'aligner.py',
    'syntax_check.py',
    'highlighter.py',
    'verification.py',
];

let pyodideInstance = null;
let pyodideReady = false;

async function mountFormatterCore(pyodide) {
    const basePath = '/home/pyodide/formatter_core';
    pyodide.FS.mkdirTree(basePath);

    for (const file of FORMATTER_CORE_FILES) {
        const response = await fetch(`./formatter_core/${file}`);
        if (!response.ok) {
            throw new Error(`加载 formatter_core/${file} 失败: ${response.status}`);
        }
        const code = await response.text();
        pyodide.FS.writeFile(`${basePath}/${file}`, code);
    }
}

async function initPyodide() {
    if (pyodideInstance) return pyodideInstance;

    if (typeof loadPyodide === 'undefined') {
        throw new Error('Pyodide 未加载，请检查网络连接');
    }

    const pyodide = await loadPyodide({
        stdout: () => {},
        stderr: () => {},
    });

    await mountFormatterCore(pyodide);

    pyodide.runPython(`
from formatter_core import format_sql_file, format_sql_file_html

def format_sql_web(sql_text):
    return {
        'formatted': format_sql_file(sql_text),
        'formatted_html': format_sql_file_html(sql_text),
    }
`);

    pyodideInstance = pyodide;
    pyodideReady = true;
    return pyodide;
}

function isPyodideReady() {
    return pyodideReady;
}

function getPyodide() {
    return pyodideInstance;
}
