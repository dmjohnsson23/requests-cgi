#!/bin/sh
# Echo CGI envs as headers and body
CONTENT=$(cat -)
printf "HTTP/1.2 200\r\n"
printf "Content-Length: ${#CONTENT}\r\n"
printf "Content-Type: text/html\r\n"
printf "ENV_REQUEST_METHOD: \"$REQUEST_METHOD\"\r\n"
printf "ENV_CONTENT_TYPE: \"$CONTENT_TYPE\"\r\n"
printf "ENV_CONTENT_LENGTH: \"$CONTENT_LENGTH\"\r\n"

printf "ENV_REMOTE_ADDR: \"$REMOTE_ADDR\"\r\n"
printf "ENV_REMOTE_PORT: \"$REMOTE_PORT\"\r\n"
printf "ENV_SERVER_PORT: \"$SERVER_PORT\"\r\n"

printf "ENV_REQUEST_URI: \"$REQUEST_URI\"\r\n"
printf "ENV_QUERY_STRING: \"$QUERY_STRING\"\r\n"

# all headers from request now available with the HTTP_ prefix
printf "ENV_HTTP_HOST: \"$HTTP_HOST\"\r\n"
printf "ENV_HTTP_USER_AGENT: \"$HTTP_USER_AGENT\"\r\n"
printf "ENV_HTTP_ACCEPT: \"$HTTP_ACCEPT\"\r\n"
printf "ENV_HTTP_REFERER: \"$HTTP_REFERER\"\r\n"

# username from basic auth (e.g. without password)
printf "ENV_REMOTE_USER: \"$REMOTE_USER\"\r\n"

printf "ENV_SCRIPT_NAME: \"$SCRIPT_NAME\"\r\n"
printf "ENV_PATH_INFO: \"$PATH_INFO\"\r\n"
printf "ENV_PATH: \"$PATH\"\r\n"
printf "ENV_PWD: \"$PWD\"\r\n"

printf "ENV_SERVER_PROTOCOL: \"$SERVER_PROTOCOL\"\r\n"
printf "ENV_SERVER_SOFTWARE: \"$SERVER_SOFTWARE\"\r\n"

printf "\r\n"
printf "$CONTENT"