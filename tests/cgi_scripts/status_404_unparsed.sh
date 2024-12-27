#!/bin/sh
CONTENT="Nothin' to see here..."

printf "HTTP/1.2 404\r\n"
printf "Content-Length: ${#CONTENT}\r\n"
printf "Content-Type: text/plain\r\n"

printf "\r\n"
printf "$CONTENT"