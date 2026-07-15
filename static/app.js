const DEFAULT_EXAMPLE = `select id, name, age from user_info where age >= 18 and status = 'active' order by created_at desc`;

const elInput = document.getElementById('sql-input');
const elOutput = document.getElementById('sql-output');
const elMessage = document.getElementById('message');
const btnFormat = document.getElementById('btn-format');
const btnCopy = document.getElementById('btn-copy');
const btnClear = document.getElementById('btn-clear');
const btnExample = document.getElementById('btn-example');
const elResizer = document.getElementById('resizer');
const elInputPanel = document.querySelector('.input-panel');
const elOutputPanel = document.querySelector('.output-panel');
const elContainer = document.querySelector('.container');

function showMessage(text, type) {
    elMessage.textContent = text;
    elMessage.className = `message ${type}`;
}

function hideMessage() {
    elMessage.className = 'message hidden';
    elMessage.textContent = '';
}

function setLoading(isLoading) {
    btnFormat.disabled = isLoading;
    btnFormat.textContent = isLoading ? '格式化中…' : '格式化';
}

function renderOutput(result, isFallback) {
    const formatted = result?.formatted || '';
    const formattedHtml = result?.formatted_html || '';

    if (formattedHtml) {
        elOutput.innerHTML = `<code>${formattedHtml}</code>`;
    } else if (formatted) {
        elOutput.innerHTML = `<code>${escapeHtml(formatted)}</code>`;
    } else {
        elOutput.innerHTML = '<code>格式化后的 SQL 将显示在这里</code>';
    }

    btnCopy.disabled = !formatted;

    if (isFallback) {
        showMessage('该段 SQL 未通过后置校验，已回退为原始文本，请人工检查。', 'warning');
    } else {
        hideMessage();
    }
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}


async function handleFormat() {
    const sql = elInput.value;

    if (!sql.trim()) {
        showMessage('请输入 SQL 后再格式化', 'error');
        return;
    }

    hideMessage();
    setLoading(true);
    elOutput.innerHTML = '<code>格式化中…</code>';

    try {
        const response = await fetch('/format', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sql }),
        });

        const data = await response.json();

        if (!data.success) {
            renderOutput(null, false);
            showMessage(data.error || '格式化失败', 'error');
            return;
        }

        const isFallback = data.formatted && data.formatted.trim() === sql.trim();
        renderOutput(data, isFallback);
    } catch (err) {
        renderOutput(null, false);
        showMessage(`请求失败：${err.message}`, 'error');
    } finally {
        setLoading(false);
    }
}

async function handleCopy() {
    const code = elOutput.querySelector('code')?.textContent || '';
    if (!code) return;

    try {
        await navigator.clipboard.writeText(code);
        showMessage('已复制到剪贴板', 'success');
        setTimeout(hideMessage, 2000);
    } catch (err) {
        showMessage('复制失败，请手动复制', 'error');
    }
}

function handleClear() {
    elInput.value = '';
    elOutput.innerHTML = '<code>格式化后的 SQL 将显示在这里</code>';
    btnCopy.disabled = true;
    hideMessage();
    elInput.focus();
}

function handleExample() {
    elInput.value = DEFAULT_EXAMPLE;
    hideMessage();
    elInput.focus();
}

btnFormat.addEventListener('click', handleFormat);
btnCopy.addEventListener('click', handleCopy);
btnClear.addEventListener('click', handleClear);
btnExample.addEventListener('click', handleExample);

elInput.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        event.preventDefault();
        handleFormat();
    }
});

function initResizer() {
    if (!elResizer || !elContainer || !elInputPanel || !elOutputPanel) return;

    let isResizing = false;

    elResizer.addEventListener('mousedown', (event) => {
        isResizing = true;
        elResizer.classList.add('dragging');
        document.body.style.userSelect = 'none';
        event.preventDefault();
    });

    document.addEventListener('mousemove', (event) => {
        if (!isResizing) return;

        const containerRect = elContainer.getBoundingClientRect();
        const minWidth = 200;
        const maxWidth = containerRect.width - minWidth - 8;
        let newWidth = event.clientX - containerRect.left;
        newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

        elInputPanel.style.flex = `0 0 ${newWidth}px`;
        elOutputPanel.style.flex = '1 1 auto';
    });

    document.addEventListener('mouseup', () => {
        if (!isResizing) return;
        isResizing = false;
        elResizer.classList.remove('dragging');
        document.body.style.userSelect = '';
    });
}

initResizer();

