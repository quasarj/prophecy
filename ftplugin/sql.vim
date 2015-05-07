
if !exists('g:vimsql_py_loaded')
    let g:vimsql_py_loaded = 1
    let g:vimsql_job_id = 0
    let g:vimsql_channel_id = 0

    if !exists('g:vimsql_env')
        let g:vimsql_env = 'convtst2'
    endif
    let s:path = expand('<sfile>:p:h')
endif

function! s:SQLSetEnv()
    let g:vimsql_env = input('Environment (connect string): ')
    redraw
    echo "Environment now set to: " . g:vimsql_env
endfunction


function! s:SQLJobHandler(job_id, data, event) abort
    if a:event == 'exit'
        let g:vimsql_job_id = 0
        let g:vimsql_channel_id = 0
        "call append(line('$'), ["exited"])
    elseif a:event == 'stdout'
        "call append(line('$'), a:data)
    elseif a:event == 'stderr'
        "call append(line('$'), a:data)
        if a:data == ["Ready"]
            " The app is now ready, so send the first command
            " that we were sitting on.
            call rpcnotify(g:vimsql_channel_id, s:type, s:args)
            unlet s:type
            unlet s:args
        endif
    endif
endfunction

function! s:VimSQLRunCommand(type, args)
    " If the app is not running, start it
    " and setup this command to be run as a callback
    if g:vimsql_job_id < 1
        let opts =  {
            \ 'on_stdout' : function('s:SQLJobHandler'),
            \ 'on_stderr' : function('s:SQLJobHandler'),
            \ 'on_exit' : function('s:SQLJobHandler'),
            \ }
        let argv = [
            \ 'python2',
            \ '-u',
            \ s:path . '/app.py',
            \ $NVIM_LISTEN_ADDRESS
            \ ]
        let g:vimsql_job_id = jobstart(argv, opts)
        " Set vars for callback, so this command will be run when
        " the app is ready.
        let s:type = a:type
        let s:args = a:args
    else
        call rpcnotify(g:vimsql_channel_id, a:type, a:args)
    endif
endfunction


command! -complete=shellcmd -nargs=0 -range RSQL <line1>,<line2>call s:RunSQLCommand(<q-args>)
function! s:RunSQLCommand(cmdline) range
    call s:VimSQLRunCommand('query', [g:vimsql_env, a:firstline, a:lastline])
    echo "Executing query against: " . g:vimsql_env
endfunction

command! -complete=shellcmd -nargs=0 -range ISQL <line1>,<line2>call s:InsertSQLCommand(<q-args>)
function! s:InsertSQLCommand(cmdline) range
    call s:VimSQLRunCommand('insertquery', [g:vimsql_env, a:firstline, a:lastline])
endfunction

command! -complete=shellcmd -nargs=0 -range ESQL <line1>,<line2>call s:ExplainSQLCommand(<q-args>)
function! s:ExplainSQLCommand(cmdline) range
    call s:VimSQLRunCommand('explain', [g:vimsql_env, a:firstline, a:lastline])
endfunction

function! s:SQLDescribeSimple()
    let a:object = expand("<cWORD>")
    call s:VimSQLRunCommand('describe_simple', [g:vimsql_env, a:object])
    echo "Describing object: " . a:object
endfunction
function! s:SQLDescribeVerbose()
    let a:object = expand("<cWORD>")
    call s:VimSQLRunCommand('describe_verbose', [g:vimsql_env, a:object])
    echo "Verbosely describing object: " . a:object
endfunction


nmap <buffer> <silent> <F9> :RSQL<CR>
nmap <buffer> <silent> - :RSQL<CR>
nmap <buffer> <silent> <leader>ee :ESQL<CR>
vmap <buffer> <silent> - :RSQL<CR>
vmap <buffer> <silent> <leader>ee :ESQL<CR>

" the sid appears to be required to call an s: func directly from a map
nmap <buffer> <silent> <leader>p :call <SID>SQLSetEnv()<CR>
nmap <buffer> <silent> <leader>d :call <SID>SQLDescribeSimple()<CR>
nmap <buffer> <silent> <leader>D :call <SID>SQLDescribeVerbose()<CR>
