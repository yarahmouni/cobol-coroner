      ******************************************************************
      * Program     : RUN-CBACT04C.CBL
      * Application : CardDemo
      * Type        : BATCH COBOL Driver Program
      * Function    : Driver program that calls CBACT04C with PARM
      ******************************************************************
      * Copyright Amazon.com, Inc. or its affiliates.
      * All Rights Reserved.
      *
      * Licensed under the Apache License, Version 2.0 (the "License").
      * You may not use this file except in compliance with the License.
      * You may obtain a copy of the License at
      *
      *    http://www.apache.org/licenses/LICENSE-2.0
      *
      * Unless required by applicable law or agreed to in writing,
      * software distributed under the License is distributed on an
      * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
      * either express or implied. See the License for the specific
      * language governing permissions and limitations under the License
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID.    RUN-CBACT04C.
       AUTHOR.        AWS.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  EXTERNAL-PARMS.
           05  PARM-LENGTH         PIC S9(04) COMP VALUE 10.
           05  PARM-DATE           PIC X(10).
      *
       PROCEDURE DIVISION.
           ACCEPT PARM-DATE FROM ENVIRONMENT 'CARDDEMO_PARM_DATE'.
           CALL 'CBACT04C' USING EXTERNAL-PARMS.
           STOP RUN.
