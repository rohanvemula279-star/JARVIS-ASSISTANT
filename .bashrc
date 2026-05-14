# ~/.bashrc
# User-specific Bash initialization file.

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# Load system-wide bashrc if available
if [ -f /etc/bash.bashrc ]; then
    . /etc/bash.bashrc
fi

# User settings
export EDITOR=vim
export LANG=en_US.UTF-8
export HISTSIZE=2000
export HISTFILESIZE=5000
export HISTCONTROL=ignoredups:erasedups
shopt -s histappend
PROMPT_DIRTRIM=2
PS1='\[\e[0;32m\]\u@\h \[\e[0;34m\]\w\[\e[0m\] $ '

# Path additions
if [ -d "$HOME/.local/bin" ] && [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
fi

# Common aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias gs='git status'
alias gd='git diff'
alias ..='cd ..'

# Enable color output for ls and grep if available
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
fi

# Source .bash_aliases if present
if [ -f "$HOME/.bash_aliases" ]; then
    . "$HOME/.bash_aliases"
fi

# Load completion if available
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
elif [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
fi
