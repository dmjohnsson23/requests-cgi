<?php
header('Content-Type: application/json');
echo json_encode([
    '$_SERVER'=>$_SERVER,
    '$_GET'=>$_GET,
    '$_POST'=>$_POST,
    '$_COOKIE'=>$_COOKIE,
    'stdin'=>file_get_contents('php://input'),
]);