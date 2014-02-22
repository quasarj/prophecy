

if !exists('g:vimsql_py_loaded')
    let s:plugin_path = escape(expand('<sfile>:p:h'), '\')
    python import vim, sys; sys.path.append(vim.eval("s:plugin_path"))
    exe 'pyfile ' . s:plugin_path . '/VimSQL.py'

    let g:vimsql_py_loaded = 1
endif

command! -complete=shellcmd -nargs=+ -range RSQL <line1>,<line2>call s:RunSQLCommand(<q-args>)
function! s:RunSQLCommand(cmdline) range
    python cmdline = vim.eval("a:cmdline")
    python from_line = vim.eval("a:firstline")
    python to_line = vim.eval("a:lastline")
    python run_sql(cmdline, from_line, to_line)
endfunction



nmap <buffer> <F9> :RSQL convtst2<CR>
nmap <buffer> - :RSQL convtst2<CR>
vmap <buffer> - :RSQL convtst2<CR>


au VimLeave * python close_sql()

