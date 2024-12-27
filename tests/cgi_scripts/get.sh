#!/bin/sh
CONTENT="You got me!"

printf "HTTP/1.2 200\r\n"
printf "Content-Length: ${#CONTENT}\r\n"
printf "Content-Type: text/plain\r\n"

printf "\r\n"
printf "$CONTENT"