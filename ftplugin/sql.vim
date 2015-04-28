
if !exists('g:vimsql_py_loaded')
    let g:vimsql_py_loaded = 1
    let g:vimsql_job_id = 0
    let g:vimsql_channel_id = 0

    if !exists('g:vimsql_env')
        let g:vimsql_env = 'convtst2'
    endif
endif

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
            \ '/home/quasar/.nvim/bundle/VimSql/ftplugin/app.py',
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
endfunction

command! -complete=shellcmd -nargs=0 -range ISQL <line1>,<line2>call s:InsertSQLCommand(<q-args>)
function! s:InsertSQLCommand(cmdline) range
    call s:VimSQLRunCommand('insertquery', [g:vimsql_env, a:firstline, a:lastline])
endfunction


nmap <buffer> <F9> :RSQL<CR>
nmap <buffer> - :RSQL<CR>
vmap <buffer> - :RSQL<CR>

nmap <buffer> <leader>e :RSQL<CR>
vmap <buffer> <leader>e :RSQL<CR>

