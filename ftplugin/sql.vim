

if !exists('g:vimsql_py_loaded')
    let g:vimsql_py_loaded = 1
endif

command! -complete=shellcmd -nargs=+ -range RSQL <line1>,<line2>call s:RunSQLCommand(<q-args>)
function! s:RunSQLCommand(cmdline) range
    call send_event(1, 'query', [a:cmdline, a:firstline, a:lastline])
endfunction

command! -complete=shellcmd -nargs=+ -range ISQL <line1>,<line2>call s:InsertSQLCommand(<q-args>)
function! s:InsertSQLCommand(cmdline) range
    call send_event(1, 'insertquery', [a:cmdline, a:firstline, a:lastline])
endfunction


nmap <buffer> <F9> :RSQL convtst2<CR>
nmap <buffer> - :RSQL convtst2<CR>
vmap <buffer> - :RSQL convtst2<CR>


