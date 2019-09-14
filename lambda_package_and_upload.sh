#!/usr/bin/env bash

if [ $1 ]; then
    zip_file=function.zip
    
    cmd="zip -g $zip_file *.py"
    echo $cmd
    $cmd
    
    cmd="cd ../lib/python3.7/site-packages"
    echo $cmd
    $cmd

    cmd="zip -r9 $OLDPWD/$zip_file ."
    echo $cmd
    $cmd

    cmd="cd $OLDPWD"
    echo $cmd
    $cmd

    cmd="du -h $zip_file"
    echo $cmd
    $cmd

    cmd="aws lambda update-function-code --function-name $1 --zip-file fileb://$zip_file"
    echo $cmd
    $cmd    
else
    echo "Must pass lambda function name"
fi
