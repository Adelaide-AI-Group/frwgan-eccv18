#!/usr/bin/env bash
_DBDIR_=./data/
_DATABASE_=sun
_CONFERENCE_=sota
_EPOCH_=epoch_85_85
_MODEL_=./experiments/$_CONFERENCE_/$_DATABASE_/cycle_wgan/classifier/checkpoint/$_EPOCH_/architecture.json

python -m routines.tester -db $_DATABASE_ -rc 1 --load_model $_MODEL_  --dataroot $_DBDIR_
